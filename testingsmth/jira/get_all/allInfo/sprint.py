import requests
from requests.auth import HTTPBasicAuth
import json
import os


def findAllSprintsFromAllBoards(domain, email, api_token, boards_file_path="all_boards.json",
                                output_file="sprints_all.json", state=None, fields=None):

    try:
        with open(boards_file_path, 'r') as f:
            boards_data = json.load(f)
    except FileNotFoundError:
        print(f"Файл {boards_file_path} не найден!")
        return {}
    except json.JSONDecodeError:
        print(f"Ошибка при чтении JSON из файла {boards_file_path}!")
        return {}

    boards = boards_data.get('values', [])
    if not boards:
        print("В файле не найдены доски!")
        return {}

    board_ids = [board['id'] for board in boards if 'id' in board]
    print(f"Найдено досок: {len(board_ids)}")
    print(f"ID досок: {board_ids}")

    all_sprints_by_board = {}

    for board_id in board_ids:
        print(f"\n{'=' * 50}")
        print(f"Получение спринтов для доски ID: {board_id}")
        print(f"{'=' * 50}")

        sprints = findAllSprints(domain, email, api_token, board_id, state=state, fields=fields)

        if sprints:
            all_sprints_by_board[str(board_id)] = {
                'board_id': board_id,
                'board_name': next((b.get('name', 'Unknown') for b in boards if b['id'] == board_id), 'Unknown'),
                'sprints': sprints,
                'sprints_count': len(sprints)
            }
        else:
            all_sprints_by_board[str(board_id)] = {
                'board_id': board_id,
                'board_name': next((b.get('name', 'Unknown') for b in boards if b['id'] == board_id), 'Unknown'),
                'sprints': [],
                'sprints_count': 0,
                'error': 'Не удалось получить спринты'
            }

    output_data = {
        'total_boards': len(all_sprints_by_board),
        'total_sprints': sum(data.get('sprints_count', 0) for data in all_sprints_by_board.values()),
        'boards': all_sprints_by_board
    }

    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=4, sort_keys=True, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"ВСЕ СПРИНТЫ СОХРАНЕНЫ В ФАЙЛ: {output_file}")
    print(f"Всего досок обработано: {len(all_sprints_by_board)}")
    print(f"Всего спринтов собрано: {output_data['total_sprints']}")
    print(f"{'=' * 60}")

    # Выводим статистику
    print("\nСТАТИСТИКА ПО ДОСКАМ:")
    for board_id, data in all_sprints_by_board.items():
        board_name = data.get('board_name', 'Unknown')
        sprints_count = data.get('sprints_count', 0)
        print(f"Доска '{board_name}' (ID: {board_id}): {sprints_count} спринтов")

    return output_data


def findAllSprints(domain, email, api_token, board_id, max_results=50, start_at=0, state=None, fields=None):

    url = f"https://{domain}/rest/agile/1.0/board/{board_id}/sprint"

    params = {
        'startAt': start_at,
        'maxResults': max_results
    }

    if state:
        params['state'] = state

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

        os.makedirs("response/boards", exist_ok=True)
        board_filename = f"response/boards/sprints_board_{board_id}.json"
        with open(board_filename, "w") as f:
            json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=False)

        print(f"Данные сохранены в файл '{board_filename}'")

        sprints = data.get('values', [])
        total_sprints = data.get('total', 0)
        is_last = data.get('isLast', True)

        all_sprints = sprints
        while not is_last and len(all_sprints) < total_sprints:
            next_start_at = len(all_sprints)
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
                next_sprints = next_data.get('values', [])
                all_sprints.extend(next_sprints)
                is_last = next_data.get('isLast', True)
            else:
                print(f"Ошибка при получении следующей страницы: {next_response.status_code}")
                break

        print(f"Найдено спринтов: {len(all_sprints)}")
        return all_sprints
    else:
        print(f"Ошибка при запросе: {response.status_code}")
        if response.status_code == 404:
            print(f"Доска с ID {board_id} не найдена!")
        elif response.status_code == 403:
            print(f"Нет доступа к доске с ID {board_id}!")
        return []


if __name__ == "__main__":
    # Конфигурационные данные
    domain = os.getenv('JIRA_URL').replace('https://', '')
    api_token = os.getenv('JIRA_API_TOKEN')
    email = os.getenv('JIRA_EMAIL')

    # Пример 1: Получить все спринты со всех досок
    print("=== ПОЛУЧЕНИЕ ВСЕХ СПРИНТОВ СО ВСЕХ ДОСОК ===")
    all_sprints_data = findAllSprintsFromAllBoards(
        domain=domain,
        email=email,
        api_token=api_token,
        boards_file_path="../filtered/response/all_boards.json",  # Путь к файлу с досками
        output_file="response/all_sprints.json"  # Файл для сохранения всех спринтов
    )

    # Пример 2: Получить только активные спринты со всех досок
    # print("\n=== ПОЛУЧЕНИЕ АКТИВНЫХ СПРИНТОВ СО ВСЕХ ДОСОК ===")
    # active_sprints_data = findAllSprintsFromAllBoards(
    #     domain=domain,
    #     email=email,
    #     api_token=api_token,
    #     boards_file_path="all_boards.json",
    #     output_file="response/sprints_active.json",
    #     state='active'  # Фильтр по активным спринтам
    # )

    # Пример 3: Получить спринты с ограниченными полями
    # print("\n=== ПОЛУЧЕНИЕ СПРИНТОВ С ОГРАНИЧЕННЫМИ ПОЛЯМИ ===")
    # selected_fields = ['id', 'name', 'state', 'startDate', 'endDate']
    # filtered_sprints_data = findAllSprintsFromAllBoards(
    #     domain=domain,
    #     email=email,
    #     api_token=api_token,
    #     boards_file_path="all_boards.json",
    #     output_file="response/sprints_filtered.json",
    #     fields=selected_fields
    # )

    # Пример 4: Получить завершенные спринты
    # print("\n=== ПОЛУЧЕНИЕ ЗАВЕРШЕННЫХ СПРИНТОВ ===")
    # closed_sprints_data = findAllSprintsFromAllBoards(
    #     domain=domain,
    #     email=email,
    #     api_token=api_token,
    #     boards_file_path="all_boards.json",
    #     output_file="response/sprints_closed.json",
    #     state='closed'
    # )