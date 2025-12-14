import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timedelta
import os


def get_jira_tasks():
    # Конфигурация
    domain = os.getenv('JIRA_URL').replace('https://', '')
    api_token = os.getenv('JIRA_API_TOKEN')
    email = os.getenv('JIRA_EMAIL')

    # Настройки запроса
    jql_query = "created >= '2024-12-12' AND created <= '2025-12-12' order by created DESC"
    output_file = "response/all_tasks.json"

    # Подготовка запроса
    url = f"https://{domain}/rest/api/3/search/jql"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    # Поля для получения
    fields = [
        "summary", "status", "assignee", "reporter", "created", "updated",
        "priority", "issuetype", "project", "labels", "description",
        "customfield_10020"  # Поле для спринтов
    ]

    # Собираем все задачи
    all_processed_tasks = []
    start_at = 0
    max_per_page = 100

    try:
        while True:
            params = {
                "jql": jql_query,
                "startAt": start_at,
                "maxResults": max_per_page,
                "fields": ",".join(fields)
            }

            response = requests.get(url, headers=headers, auth=auth, params=params, timeout=30)

            if response.status_code != 200:
                print(f"Ошибка API: {response.status_code}")
                return []

            data = response.json()
            issues = data.get('issues', [])

            if not issues:
                break

            # Обрабатываем каждую задачу
            for task in issues:
                processed_task = process_single_task(task)
                if processed_task:
                    all_processed_tasks.append(processed_task)

            # Проверяем, есть ли еще задачи
            total = data.get('total', 0)
            if start_at + len(issues) >= total:
                break

            start_at += max_per_page

    except Exception as e:
        print(f"Ошибка при получении задач: {e}")
        return []

    # Сохраняем в файл
    if all_processed_tasks:
        save_to_file(all_processed_tasks, output_file, jql_query)

    return all_processed_tasks


def process_single_task(task):
    try:
        fields = task.get('fields', {})

        # Получаем sprint_id
        sprint_id = None
        customfield = fields.get('customfield_10020')

        if customfield:
            if isinstance(customfield, list) and len(customfield) > 0:
                last_sprint = customfield[-1]
                if isinstance(last_sprint, dict):
                    sprint_id = last_sprint.get('id')
                elif isinstance(last_sprint, str):
                    # Парсим строковый формат спринта
                    import re
                    match = re.search(r'@(\d+)\[', last_sprint)
                    if match:
                        try:
                            sprint_id = int(match.group(1))
                        except:
                            sprint_id = None

        # Собираем результат
        result = {
            "task_key": task.get('key', ''),
            "summary": fields.get('summary', ''),
            "priority_name": fields.get('priority', {}).get('name', '') if fields.get('priority') else '',
            "project_key": fields.get('project', {}).get('key', '') if fields.get('project') else '',
            "reporter_name": fields.get('reporter', {}).get('displayName', '') if fields.get('reporter') else '',
            "assignee_name": fields.get('assignee', {}).get('displayName', '') if fields.get('assignee') else '',
            "issue_type": fields.get('issuetype', {}).get('name', '') if fields.get('issuetype') else '',
            "hierarchyLevel": fields.get('issuetype', {}).get('hierarchyLevel', 0) if fields.get('issuetype') else 0,
            "status_key": fields.get('status', {}).get('statusCategory', {}).get('key', '') if fields.get('status',
                                                                                                          {}).get(
                'statusCategory') else '',
            "sprint_id": sprint_id
        }

        # Конвертируем типы
        if result["hierarchyLevel"] is not None:
            try:
                result["hierarchyLevel"] = int(result["hierarchyLevel"])
            except:
                result["hierarchyLevel"] = 0

        return result

    except Exception:
        return None


def save_to_file(tasks, filename, jql_query):
    try:
        # Создаем директорию если нужно
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        # Подготавливаем данные
        result_data = {
            "metadata": {
                "total_tasks": len(tasks),
                "jql_query": jql_query,
                "retrieved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "tasks": tasks
        }

        # Сохраняем
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        print(f"Успешно загружено {len(tasks)} задач в файл {filename}")
        return True

    except Exception as e:
        print(f"Ошибка при сохранении файла: {e}")
        return False


def main():
    tasks = get_jira_tasks()

    if tasks:
        print("✅ Операция выполнена успешно")
    else:
        print("❌ Не удалось получить задачи")


# Запуск
if __name__ == "__main__":
    main()