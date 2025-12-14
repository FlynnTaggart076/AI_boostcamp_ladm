import requests
from requests.auth import HTTPBasicAuth
import json
import os


def get_all_boards():
    """
    Получает все доски и сохраняет в файл
    Возвращает: список досок с нужными полями
    """
    # Конфигурация
    domain = os.getenv('JIRA_URL').replace('https://', '')
    api_token = os.getenv('JIRA_API_TOKEN')
    email = os.getenv('JIRA_EMAIL')
    output_file = "response/all_boards.json"

    # Получаем все доски через API
    boards = get_boards_from_api(domain, email, api_token)

    # Сохраняем в файл
    if boards:
        save_boards_to_file(boards, output_file)
        print(f"Успешно загружено {len(boards)} досок")

    return boards


def get_boards_from_api(domain, email, api_token):
    """
    Получает доски через API и оставляет только нужные поля
    """
    url = f"https://{domain}/rest/agile/1.0/board"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    all_boards = []
    start_at = 0
    max_results = 50

    try:
        while True:
            params = {'startAt': start_at, 'maxResults': max_results}

            response = requests.get(url, headers=headers, auth=auth, params=params, timeout=30)

            if response.status_code != 200:
                print(f"Ошибка API: {response.status_code}")
                break

            data = response.json()
            boards = data.get('values', [])

            if not boards:
                break

            # Обрабатываем каждую доску - оставляем только нужные поля
            for board in boards:
                processed_board = {
                    "id": board.get('id'),
                    "name": board.get('name', ''),
                    "projectKey": board.get('location', {}).get('projectKey', '')
                }
                all_boards.append(processed_board)

            # Проверяем, есть ли еще доски
            total = data.get('total', 0)
            if start_at + len(boards) >= total or data.get('isLast', True):
                break

            start_at += max_results

    except Exception as e:
        print(f"Ошибка при получении досок: {e}")
        return []

    return all_boards


def save_boards_to_file(boards, filename):
    """
    Сохраняет доски в JSON файл
    """
    try:
        # Создаем директорию если нужно
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        # Подготавливаем данные
        result_data = {
            "metadata": {
                "total_boards": len(boards)
            },
            "boards": boards
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
    # Получаем и сохраняем доски
    boards = get_all_boards()

    if boards:
        print("✅ Операция выполнена успешно")
    else:
        print("❌ Не удалось получить доски")


# Запуск
if __name__ == "__main__":
    main()