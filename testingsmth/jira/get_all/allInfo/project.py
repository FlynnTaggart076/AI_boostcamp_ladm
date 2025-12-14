import os

import requests
from requests.auth import HTTPBasicAuth
import json


def findAllProjects(domain, email, api_token, fields=None):
    url = f"https://{domain}/rest/api/3/project"

    params = {}
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
        dump = json.dumps(data, sort_keys=True, indent=4, separators=(",", ": "))

        with open("response/all_projects.json", "w") as f:
            f.write(dump)

        print("Данные успешно сохранены в файл 'response/all_projects.json'")

        print(f"Всего проектов: {len(data)}")
        print("\nСписок проектов:")

        for project in data:
            if fields:
                project_info = []
                for field in fields:
                    if field in project:
                        project_info.append(f"{field}: {project[field]}")
                print(f"- {' | '.join(project_info)}")
            else:
                key = project.get('key', 'N/A')
                name = project.get('name', 'N/A')
                print(f"- {key}: {name}")

        return data
    else:
        print(f"Ошибка при запросе: {response.status_code}")
        print(response.text)
        return None


if __name__ == "__main__":
    domain = os.getenv('JIRA_URL').replace('https://', '')
    api_token = os.getenv('JIRA_API_TOKEN')
    email = os.getenv('JIRA_EMAIL')

    print("=== Получение всех проектов со всеми полями ===")
    all_projects = findAllProjects(domain, email, api_token)

    # print("\n=== Получение проектов с ограниченным набором полей ===")
    # # Доступные поля можно найти в документации Jira API
    # # Некоторые полезные поля: key, name, id, projectTypeKey, simplified, style, isPrivate
    # selected_fields = ['key', 'name', 'projectTypeKey', 'id']
    # filtered_projects = findAllProjects(domain, email, api_token, fields=selected_fields)
