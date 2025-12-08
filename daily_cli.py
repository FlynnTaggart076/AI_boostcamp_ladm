# daily_cli.py
import os
from qwen_agent import parse_daily

QWEN_URL = "https://qwen1.product.nova.neurotech.k2.cloud/"
QWEN_TOKEN = os.getenv("QWEN_API_TOKEN", "HLYsERkS69fa05xfII")


def ask_one_person(name: str) -> dict:
    """Спрашиваем одного человека и возвращаем разобранный daily-словарь."""
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
    daily["name"] = name  # добавим имя, пригодится для дайджеста
    return daily


def main():
    # пока список имён захардкожен — потом можно читать из файла/БД/конфига
    team = ["Вася", "Мила", "Саша"]

    all_dailies: list[dict] = []

    for name in team:
        d = ask_one_person(name)
        all_dailies.append(d)

    print("\n=== Все daily (структурировано) ===")
    for d in all_dailies:
        print(d)


if __name__ == "__main__":
    main()

