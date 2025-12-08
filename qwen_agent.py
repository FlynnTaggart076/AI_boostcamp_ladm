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
        'Если блокеров нет, то "blockers"="", "has_blockers"=false, "critical"=false.\n\n'
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


# --- CLI-обёртка для запуска из PyCharm ---


if __name__ == "__main__":
    # можно захардкодить, можно вынести в env-переменные
    QWEN_URL = "https://qwen1.product.nova.neurotech.k2.cloud/"
    # лучше так: экспортировать QWEN_API_TOKEN в окружение
    QWEN_TOKEN = os.getenv("QWEN_API_TOKEN", "HLYsERkS69fa05xfII")

    print("Введи текст отчёта разработчика (один абзац).")
    user_input = input("> ")

    try:
        result = call_qwen(
            user_text=user_input,
            url=QWEN_URL,
            api_token=QWEN_TOKEN,
            temperature=0.01,
            max_new_tokens=128,
        )
        print("\nОтвет модели:")
        print(result)
    except Exception as e:
        print("Ошибка при вызове Qwen:", e)
