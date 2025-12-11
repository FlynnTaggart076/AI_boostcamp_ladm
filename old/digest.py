# digest.py
import os
import json
import requests
import urllib3
from .qwen_agent import extract_text_from_response
from config import QWEN_URL, QWEN_TOKEN
from config import QWEN_URL, QWEN_TOKEN


def build_digest(
    dailies: list[dict],
    url: str = QWEN_URL,
    api_token: str | None = QWEN_TOKEN,
    temperature: float = 0.2,
    max_new_tokens: int = 512,
) -> str:
    """
    Собирает текстовый дайджест по списку daily-словарей.

    dailies: список словарей вида:
    {
      "name": "Антон",
      "yesterday": "...",
      "today": "...",
      "blockers": "...",
      "has_blockers": true/false,
      "critical": true/false
    }
    """
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Превратим dailies в JSON-строку, чтобы красиво скормить модели
    dailies_json = json.dumps(dailies, ensure_ascii=False, indent=2)

    prompt = (
        "Ты — ассистент тимлида разработки.\n"
        "Тебе приходит список структурированных daily-отчётов в формате JSON.\n"
        "Твоя задача — сделать краткий дайджест в Markdown.\n\n"
        "Каждый объект в JSON имеет поля:\n"
        '- "name": имя разработчика\n'
        '- "yesterday": что делал вчера\n'
        '- "today": что делает сегодня\n'
        '- "blockers": блокеры\n'
        '- "has_blockers": есть ли блокеры (true/false)\n'
        '- "critical": критичный ли блокер (true/false)\n\n'
        "Формат ответа:\n"
        "## Общая картина\n"
        "- 2–4 предложения о прогрессе команды.\n\n"
        "## По людям\n"
        "- Имя: вчера ..., сегодня ...\n\n"
        "## Блокеры\n"
        "- Имя: описание блокера (помечай критичные блокеры).\n\n"
        "Если блокеров нет ни у кого — в секции Блокеры напиши: «Блокеров нет».\n\n"
        "Вот JSON с данными:\n"
        f"{dailies_json}\n\n"
        "Напиши дайджест в этом формате:"
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

    raw_text = extract_text_from_response(data)
    return raw_text.strip()