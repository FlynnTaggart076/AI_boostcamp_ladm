import os

import requests
import json
from requests.auth import HTTPBasicAuth


def get_all_users(domain, email, api_token, account_type=""):
    """
    Получает всех пользователей из Jira
    :param domain: Домен Jira (например: mavartemkz2007.atlassian.net)
    :param email: Email для аутентификации
    :param api_token: API токен
    :param account_type: "" - все пользователи, "app" - только приложения, "atlassian" - только пользователи
    :return: Список пользователей или None при ошибке
    """
    # Настройки запроса
    url = f"https://{domain}/rest/api/3/users/search"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    # Получаем всех пользователей с пагинацией
    all_users = []
    start_at = 0
    max_results = 100  # Максимум 100 за запрос

    print(f"Начинаю получать пользователей...")

    while True:
        # Параметры запроса
        params = {
            "startAt": start_at,
            "maxResults": max_results
        }

        # Отправляем запрос
        response = requests.get(url, auth=auth, headers=headers, params=params)

        # Проверяем ответ
        if response.status_code != 200:
            print(f"Ошибка: {response.status_code}")
            print(f"Текст ошибки: {response.text}")
            return None

        # Парсим JSON
        users = json.loads(response.text)

        # Если пользователей нет, выходим из цикла
        if not users:
            break

        # Фильтруем по типу аккаунта если нужно
        if account_type:
            filtered_users = [user for user in users if user.get("accountType", "") == account_type]
            all_users.extend(filtered_users)
            print(f"Загружено {len(filtered_users)} пользователей типа '{account_type}' (всего в ответе: {len(users)})")
        else:
            all_users.extend(users)
            print(f"Загружено {len(users)} пользователей")

        # Если получено меньше чем запросили - значит это последняя страница
        if len(users) < max_results:
            break

        # Переходим к следующей странице
        start_at += max_results

    # Сохраняем результат в файл
    filename = "response/all_users.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_users, f, ensure_ascii=False, indent=2)

    # Выводим статистику
    print(f"\n=== Результат ===")
    print(f"Всего пользователей: {len(all_users)}")

    if all_users:
        print("\nПервые 10 пользователей:")
        for i, user in enumerate(all_users[:10], 1):
            name = user.get("displayName", "Без имени")
            email = user.get("emailAddress", "Нет email")
            acc_type = user.get("accountType", "Неизвестно")
            active = "✓" if user.get("active", False) else "✗"
            print(f"{i}. {name} ({email}) | Тип: {acc_type} | Активен: {active}")

    return all_users


# Пример использования
if __name__ == "__main__":
    # Ваши данные
    DOMAIN = os.getenv('JIRA_URL').replace('https://', '')
    EMAIL = os.getenv('JIRA_API_TOKEN')
    API_TOKEN = os.getenv('JIRA_EMAIL')

    print("=== Получение пользователей из Jira ===")
    print("Выберите тип пользователей:")
    print("1. Все пользователи (нажмите Enter)")
    print("2. Только обычные пользователи (atlassian)")
    print("3. Только приложения (app)")

    choice = input("Ваш выбор (1/2/3): ").strip()

    account_type_map = {
        "": "",
        "1": "",
        "2": "atlassian",
        "3": "app"
    }

    selected_type = account_type_map.get(choice, "")

    # Получаем пользователей
    users = get_all_users(DOMAIN, EMAIL, API_TOKEN, selected_type)

    if users is not None:
        print(f"\nФайл сохранен как: all_users.json")