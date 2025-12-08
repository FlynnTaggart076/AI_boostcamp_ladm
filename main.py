# main.py
import os
from app.qwen_agent import parse_daily
from app.digest import build_digest
from config import QWEN_URL, QWEN_TOKEN


def ask_one_person(name: str) -> dict:
    print(f"\n=== Daily для {name} ===")
    print("Напиши одним абзацем: что делал вчера / что делаешь сегодня / какие блокеры.")
    text = input("> ")

    daily = parse_daily(
        user_text=text,
        url=QWEN_URL,
        api_token=QWEN_TOKEN,
        temperature=0.01,
        max_new_tokens=128,
    )
    daily["name"] = name
    return daily


def main():
    team = ["Вася", "Мила", "Саша"]
    all_dailies: list[dict] = []

    for name in team:
        d = ask_one_person(name)
        all_dailies.append(d)

    print("\n=== Все daily (структурировано) ===")
    for d in all_dailies:
        print(d)

    # 👇 добавляем вызов дайджеста
    print("\n=== Дайджест для тимлида ===\n")
    digest_text = build_digest(all_dailies)   # url и token берутся по умолчанию из config.py
    print(digest_text)


if __name__ == "__main__":
    main()
