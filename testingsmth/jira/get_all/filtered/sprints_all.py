import requests
from requests.auth import HTTPBasicAuth
import json
import os

def get_all_sprints():
    """
    Получает все спринты из всех досок и сохраняет в файл
    Возвращает: список спринтов с нужными полями
    """
    # Конфигурация
    domain = os.getenv('JIRA_URL').replace('https://', '')
    api_token = os.getenv('JIRA_API_TOKEN')
    email = os.getenv('JIRA_EMAIL')

    # Файлы
    boards_file = "response/all_boards.json"
    output_file = "response/all_sprints.json"

    # Читаем файл с досками
    boards = read_boards_file(boards_file)
    if not boards:
        print(f"Не удалось прочитать файл {boards_file}")
        return []

    # Получаем спринты со всех досок
    all_sprints = []
    for board in boards:
        board_id = board.get('id')
        if board_id:
            sprints = get_sprints_from_board(domain, email, api_token, board_id)
            all_sprints.extend(sprints)

    # Сохраняем в файл
    if all_sprints:
        save_sprints_to_file(all_sprints, output_file)
        print(f"Успешно загружено {len(all_sprints)} спринтов")

    return all_sprints


def read_boards_file(filename):
    """
    Читает файл с досками
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Извлекаем доски из разных возможных структур
        boards = data.get('values', [])
        if not boards:
            boards = data.get('boards', [])
        if not boards and isinstance(data, list):
            boards = data

        return boards

    except FileNotFoundError:
        print(f"Файл {filename} не найден")
        return []
    except json.JSONDecodeError:
        print(f"Ошибка чтения JSON из файла {filename}")
        return []
    except Exception as e:
        print(f"Ошибка при чтении файла {filename}: {e}")
        return []


def get_sprints_from_board(domain, email, api_token, board_id):
    """
    Получает спринты с конкретной доски
    """
    url = f"https://{domain}/rest/agile/1.0/board/{board_id}/sprint"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    all_sprints = []
    start_at = 0
    max_results = 50

    try:
        while True:
            params = {'startAt': start_at, 'maxResults': max_results}

            response = requests.get(url, headers=headers, auth=auth, params=params, timeout=30)

            if response.status_code != 200:
                break

            data = response.json()
            sprints = data.get('values', [])

            if not sprints:
                break

            # Обрабатываем каждый спринт - оставляем только нужные поля
            for sprint in sprints:
                processed_sprint = {
                    "id": sprint.get('id'),
                    "name": sprint.get('name', ''),
                    "state": sprint.get('state', ''),
                    "originBoardId": sprint.get('originBoardId')
                }
                all_sprints.append(processed_sprint)

            # Проверяем, есть ли еще спринты
            if data.get('isLast', True):
                break

            start_at += max_results

    except Exception:
        pass  # Игнорируем ошибки для конкретной доски

    return all_sprints


def save_sprints_to_file(sprints, filename):
    """
    Сохраняет спринты в JSON файл
    """
    try:
        # Создаем директорию если нужно
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        # Подготавливаем данные
        result_data = {
            "metadata": {
                "total_sprints": len(sprints)
            },
            "sprints": sprints
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
    # Получаем и сохраняем спринты
    sprints = get_all_sprints()

    if sprints:
        print("✅ Операция выполнена успешно")
    else:
        print("❌ Не удалось получить спринты")


# Запуск
if __name__ == "__main__":
    main()