import os

import requests
from requests.auth import HTTPBasicAuth
import json


def findAllBoards(domain, email, api_token, max_results=50, start_at=0, board_type=None, fields=None):
    url = f"https://{domain}/rest/agile/1.0/board"

    params = {
        'startAt': start_at,
        'maxResults': max_results
    }

    if board_type:
        params['type'] = board_type

    if fields:
        params['fields'] = ','.join(fields)

    auth = HTTPBasicAuth(email, api_token)

    headers = {
        "Accept": "application/json"
    }

    response = requests.request(
        "GET",
        url,
        headers=headers,
        auth=auth,
        params=params
    )

    print(f"Response status code: {response.status_code}")

    if response.status_code == 200:
        data = json.loads(response.text)

        # Сохраняем ответ в JSON файл
        dump = json.dumps(data, sort_keys=True, indent=4, separators=(",", ": "))
        with open("../filtered/response/all_boards.json", "w") as f:
            f.write(dump)

        print("Данные успешно сохранены в файл 'boards_all.json'")

        boards = data.get('values', [])
        total_boards = data.get('total', 0)
        is_last = data.get('isLast', True)

        all_boards = boards
        while not is_last and len(all_boards) < total_boards:
            next_start_at = len(all_boards)
            params['startAt'] = next_start_at

            next_response = requests.request(
                "GET",
                url,
                headers=headers,
                auth=auth,
                params=params
            )

            if next_response.status_code == 200:
                next_data = json.loads(next_response.text)
                next_boards = next_data.get('values', [])
                all_boards.extend(next_boards)
                is_last = next_data.get('isLast', True)
            else:
                print(f"Ошибка при получении следующей страницы: {next_response.status_code}")
                break

        print(f"Всего досок: {len(all_boards)}")
        print("\nСписок досок:")

        for board in all_boards:
            if fields:
                board_info = []
                for field in fields:
                    if field in board:
                        board_info.append(f"{field}: {board[field]}")
                print(f"- {' | '.join(board_info)}")
            else:
                board_id = board.get('id', 'N/A')
                board_name = board.get('name', 'N/A')
                board_type = board.get('type', 'N/A')
                print(f"- ID: {board_id}, Название: {board_name}, Тип: {board_type}")

        return all_boards
    else:
        print(f"Ошибка при запросе: {response.status_code}")
        print(response.text)
        return None


if __name__ == "__main__":
    domain = os.getenv('JIRA_URL').replace('https://', '')
    api_token = os.getenv('JIRA_API_TOKEN')
    email = os.getenv('JIRA_EMAIL')

    print("=== Получение всех досок со всеми полями ===")
    all_boards = findAllBoards(domain, email, api_token)

    # # Пример 2: Получить только доски типа Kanban
    # print("\n=== Получение только Kanban досок ===")
    # kanban_boards = findAllBoards(domain, email, api_token, board_type='kanban')
    #
    # # Пример 3: Получить только определенные поля
    # print("\n=== Получение досок с ограниченным набором полей ===")
    # selected_fields = ['id', 'name', 'type', 'location']
    # filtered_boards = findAllBoards(domain, email, api_token, fields=selected_fields)
    #
    # # Пример 4: Получить только Scrum доски с основными полями
    # print("\n=== Получение Scrum досок с основными полями ===")
    # scrum_boards = findAllBoards(
    #     domain,
    #     email,
    #     api_token,
    #     board_type='scrum',
    #     fields=['id', 'name', 'type']
    # )
    #
    # # Пример 5: Получить все доски с пагинацией (большие объемы)
    # print("\n=== Получение всех досок с пагинацией ===")
    # # Получаем по 20 досок за раз (для демонстрации пагинации)
    # paginated_boards = findAllBoards(domain, email, api_token, max_results=20)