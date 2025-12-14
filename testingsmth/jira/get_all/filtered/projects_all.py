import requests
from requests.auth import HTTPBasicAuth
import json
import os


def get_all_projects():
    domain = os.getenv('JIRA_URL').replace('https://', '')
    api_token = os.getenv('JIRA_API_TOKEN')
    email = os.getenv('JIRA_EMAIL')
    output_file = "response/all_projects.json"

    # Получаем все проекты через API
    projects = get_projects_from_api(domain, email, api_token)

    # Сохраняем в файл
    if projects:
        save_projects_to_file(projects, output_file)
        print(f"Успешно загружено {len(projects)} проектов")

    return projects


def get_projects_from_api(domain, email, api_token):
    url = f"https://{domain}/rest/api/3/project"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, auth=auth, timeout=30)

        if response.status_code != 200:
            print(f"Ошибка API: {response.status_code}")
            return []

        data = response.json()

        processed_projects = []
        for project in data:
            processed_project = {
                "key": project.get('key', ''),
                "name": project.get('name', ''),
                "projectTypeKey": project.get('projectTypeKey', '')
            }
            processed_projects.append(processed_project)

        return processed_projects

    except Exception as e:
        print(f"Ошибка при получении проектов: {e}")
        return []


def save_projects_to_file(projects, filename):
    """
    Сохраняет проекты в JSON файл
    """
    try:
        # Создаем директорию если нужно
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        # Подготавливаем данные
        result_data = {
            "metadata": {
                "total_projects": len(projects)
            },
            "projects": projects
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
    # Получаем и сохраняем проекты
    projects = get_all_projects()

    if projects:
        print("✅ Операция выполнена успешно")
    else:
        print("❌ Не удалось получить проекты")


# Запуск
if __name__ == "__main__":
    main()