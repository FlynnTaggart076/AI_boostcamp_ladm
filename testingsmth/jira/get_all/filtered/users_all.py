import requests
from requests.auth import HTTPBasicAuth
import json
import os


def get_all_users():
    """
    Получает всех пользователей и сохраняет в файл
    Возвращает: список пользователей с нужными полями
    """
    # Конфигурация
    domain = os.getenv('JIRA_URL').replace('https://', '')
    api_token = os.getenv('JIRA_API_TOKEN')
    email = os.getenv('JIRA_EMAIL')
    output_file = "response/all_users.json"

    # Получаем всех пользователей через API
    users = get_users_from_api(domain, email, api_token)

    # Сохраняем в файл
    if users:
        save_users_to_file(users, output_file)
        print(f"Успешно загружено {len(users)} пользователей")

    return users


def get_users_from_api(domain, email, api_token):
    """
    Получает пользователей через API и оставляет только нужные поля
    """
    url = f"https://{domain}/rest/api/3/users/search"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    all_users = []
    start_at = 0
    max_results = 100

    try:
        while True:
            params = {'startAt': start_at, 'maxResults': max_results}

            response = requests.get(url, headers=headers, auth=auth, params=params, timeout=30)

            if response.status_code != 200:
                print(f"Ошибка API: {response.status_code}")
                break

            users_data = response.json()

            if not users_data:
                break

            # Обрабатываем каждого пользователя - оставляем только нужные поля
            for user in users_data:
                # Добавляем проверку типа аккаунта - только "atlassian"
                if user.get('accountType') == 'atlassian':
                    processed_user = {
                        "displayName": user.get('displayName', ''),
                        "emailAddress": user.get('emailAddress', '')
                    }
                    all_users.append(processed_user)

            # Проверяем, есть ли еще пользователи
            if len(users_data) < max_results:
                break

            start_at += max_results

    except Exception as e:
        print(f"Ошибка при получении пользователей: {e}")
        return []

    return all_users


def save_users_to_file(users, filename):
    """
    Сохраняет пользователей в JSON файл
    """
    try:
        # Создаем директорию если нужно
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        # Подготавливаем данные
        result_data = {
            "metadata": {
                "total_users": len(users)
            },
            "users": users
        }

        # Сохраняем
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        return True

    except Exception as e:
        print(f"Ошибка при сохранении файла: {e}")
        return False


def main():
    """
    Основная функция запуска
    """
    # Получаем и сохраняем пользователей
    users = get_all_users()

    if users:
        print("✅ Операция выполнена успешно")
    else:
        print("❌ Не удалось получить пользователей")


# Запуск
if __name__ == "__main__":
    main()