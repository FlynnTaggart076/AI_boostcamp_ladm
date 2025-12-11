import os
import json
import requests
import urllib3


# --- вспомогательные функции ---


def extract_text_from_response(data) -> str:
    """Достаём текст из стандартного ответа Qwen/TGI."""
    try:
        # формат list[{"generated_text": "..."}]
        if isinstance(data, list) and data:
            item = data[0]
            if isinstance(item, dict):
                if "generated_text" in item:
                    return str(item["generated_text"])
                if "text" in item:
                    return str(item["text"])
            return str(item)

        # формат dict
        if isinstance(data, dict):
            for key in ["generated_text", "text", "output_text"]:
                if key in data:
                    return str(data[key])
            return json.dumps(data, ensure_ascii=False)

        # всё остальное
        return str(data)
    except Exception:
        return str(data)


def extract_json_from_raw(raw: str) -> str:
    """
    Вырезаем JSON между первой { и последней }, валидируем.
    Поскольку в промпте фигурных скобок нет, это должен быть ответ модели.
    """
    raw = raw.strip()
    if not raw:
        return "Model returned empty response"

    if "{" in raw and "}" in raw:
        start = raw.find("{")
        end = raw.rfind("}")
        if end > start:
            candidate = raw[start: end + 1].strip()
            try:
                obj = json.loads(candidate)
                # нормализуем JSON
                return json.dumps(obj, ensure_ascii=False)
            except Exception:
                # если JSON кривой — вернём как есть
                return candidate

    # если вообще нет фигурных скобок — вернём сырой текст
    return raw


# --- основная функция вызова Qwen ---


def call_qwen(
    user_text: str,
    url: str,
    api_token: str | None,
    temperature: float = 0.01,
    max_new_tokens: int = 256,
) -> str:
    """
    Отправляет текст разработчика в Qwen и возвращает строку (чистый JSON или текст ошибки).
    """
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    user_text = user_text.strip()

    # ВЕСЬ промпт собираем здесь (как в твоём компоненте)
    prompt = (
        "Ты — сервис, который превращает отчёты разработчиков в JSON.\n\n"
        "На вход ты получаешь один абзац текста, где разработчик описывает, "
        "что он делал вчера, что будет делать сегодня и какие у него есть блокеры.\n\n"
        'Верни строго один валидный JSON-объект с полями '
        '"yesterday", "today", "blockers", "has_blockers", "critical". '
        "Никакого дополнительного текста.\n"
        'Если блокеров нет, то "blockers" = "", "has_blockers" = false, "critical" = false.\n\n'
        "Если в тексте есть слова \"Блокер\" или \"блокер\", всегда считай текст после этого слова "
        "(до конца предложения или строки) описанием блокера и заполняй поле \"blockers\". "
        "В этом случае has_blockers = true. "
        "Неважно, каким знаком препинания отделено слово \"Блокер\" — точкой, запятой, тире и т.п.\n\n"
        f"Текст разработчика:\n{user_text}\n\n"
        "Ответ:"
    )

    headers = {"Content-Type": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    body = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": int(max_new_tokens),
            "do_sample": False,
            "temperature": float(temperature),
        },
    }

    resp = requests.post(
        url,
        json=body,
        headers=headers,
        verify=False,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    # можно печатать для отладки, если нужно
    # print("RAW:", json.dumps(data, ensure_ascii=False))

    raw_text = extract_text_from_response(data)
    cleaned = extract_json_from_raw(raw_text)
    return cleaned.strip()


def parse_daily(
    user_text: str,
    url: str,
    api_token: str | None,
    temperature: float = 0.01,
    max_new_tokens: int = 256,
) -> dict:
    """
    Обертка над call_qwen:
    - вызывает модель с текстом daily
    - парсит строку-JSON в Python-словарь
    """
    raw = call_qwen(
        user_text=user_text,
        url=url,
        api_token=api_token,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
    )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # если модель вернула невалидный JSON — кидаем понятную ошибку
        raise ValueError(f"Модель вернула невалидный JSON: {raw!r}")

    # на всякий случай добавим дефолтные поля, чтобы дальше не падать
    defaults = {
        "yesterday": "",
        "today": "",
        "blockers": "",
        "has_blockers": False,
        "critical": False,
    }
    for k, v in defaults.items():
        data.setdefault(k, v)

    return data