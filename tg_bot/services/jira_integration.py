"""
Модуль для интеграции с Jira API
"""
import logging
import requests
from typing import Dict, Optional, List
from datetime import datetime
from tg_bot.config.settings import config

logger = logging.getLogger(__name__)


class JiraIntegration:
    """Класс для работы с Jira API"""

    def __init__(self):
        self.base_url = config.JIRA_URL
        self.auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def find_user_by_display_name(self, display_name: str) -> Optional[Dict]:
        """
        Поиск пользователя по имени (используя корпоративный аккаунт)

        Args:
            display_name: Отображаемое имя пользователя в Jira

        Returns:
            Словарь с информацией о пользователе или None
        """
        try:
            # Ищем пользователя по имени (displayName)
            url = f"{self.base_url}/rest/api/3/user/search"

            params = {
                'query': display_name,
                'maxResults': 50
            }

            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                users = response.json()

                # Ищем точное совпадение по displayName
                for user in users:
                    if user.get('displayName', '').lower() == display_name.lower():
                        return {
                            'account_id': user.get('accountId'),
                            'display_name': user.get('displayName'),
                            'email_address': user.get('emailAddress'),
                            'active': user.get('active', False)
                        }

                # Если точного совпадения нет, возвращаем первого пользователя
                if users:
                    user = users[0]
                    return {
                        'account_id': user.get('accountId'),
                        'display_name': user.get('displayName'),
                        'email_address': user.get('emailAddress'),
                        'active': user.get('active', False)
                    }

            logger.warning(f"Пользователь Jira '{display_name}' не найден")
            return None

        except Exception as e:
            logger.error(f"Ошибка поиска пользователя Jira: {e}")
            return None

    def get_user_projects_by_account_id(self, account_id: str) -> List[Dict]:
        """
        Получение проектов пользователя по accountId

        Args:
            account_id: Account ID пользователя в Jira

        Returns:
            Список проектов с задачами
        """
        try:
            # Ищем задачи, назначенные пользователю по accountId
            url = f"{self.base_url}/rest/api/3/search/jql"

            # Используем accountId в JQL
            jql = f'assignee = "{account_id}" AND status != Done'

            payload = {
                'jql': jql,
                'maxResults': 50,
                'fields': ['project', 'sprint', 'summary', 'assignee']
            }

            response = requests.post(
                url,
                headers=self.headers,
                auth=self.auth,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                issues = data.get('issues', [])
                projects = {}

                print(f"Найдено задач для пользователя: {len(issues)}")

                for issue in issues:
                    project_data = issue['fields']['project']
                    project_key = project_data['key']

                    if project_key not in projects:
                        projects[project_key] = {
                            'id': project_data['id'],
                            'key': project_key,
                            'name': project_data['name'],
                            'tasks': []
                        }

                    # Извлекаем информацию о спринте
                    sprint_data = issue['fields'].get('sprint')
                    sprint_info = None

                    if sprint_data:
                        if isinstance(sprint_data, list) and sprint_data:
                            active_sprints = [s for s in sprint_data
                                            if s.get('state') == 'active']
                            if active_sprints:
                                sprint_info = active_sprints[0]
                        elif isinstance(sprint_data, dict):
                            sprint_info = sprint_data

                    task_info = {
                        'key': issue['key'],
                        'summary': issue['fields']['summary'],
                        'sprint': sprint_info
                    }

                    projects[project_key]['tasks'].append(task_info)

                print(f"Проектов найдено: {len(projects)}")
                return list(projects.values())

            print(f"Ошибка запроса: {response.status_code}")
            return []

        except Exception as e:
            print(f"Исключение при получении проектов: {e}")
            return []

    def get_active_sprints(self, project_key: str) -> List[Dict]:
        """
        Получение активных спринтов в проекте

        Args:
            project_key: Ключ проекта

        Returns:
            Список активных спринтов
        """
        try:
            url = f"{self.base_url}/rest/agile/1.0/board"

            params = {
                'type': 'scrum',
                'projectKeyOrId': project_key
            }

            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                boards = response.json().get('values', [])
                sprints = []

                for board in boards:
                    sprints_url = f"{self.base_url}/rest/agile/1.0/board/{board['id']}/sprint"

                    sprints_response = requests.get(
                        sprints_url,
                        headers=self.headers,
                        auth=self.auth,
                        timeout=10
                    )

                    if sprints_response.status_code == 200:
                        board_sprints = sprints_response.json().get('values', [])
                        active_sprints = [s for s in board_sprints
                                        if s.get('state') == 'active']
                        sprints.extend(active_sprints)

                return sprints

            return []

        except Exception as e:
            logger.error(f"Ошибка получения спринтов: {e}")
            return []

    def get_project_details(self, project_key: str) -> Optional[Dict]:
        """
        Получение детальной информации о проекте

        Args:
            project_key: Ключ проекта

        Returns:
            Информация о проекте или None
        """
        try:
            url = f"{self.base_url}/rest/api/3/project/{project_key}"

            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                timeout=10
            )

            if response.status_code == 200:
                project_data = response.json()
                return {
                    'id': project_data['id'],
                    'key': project_data['key'],
                    'name': project_data['name'],
                    'description': project_data.get('description', ''),
                    'lead': project_data.get('lead', {}).get('displayName', ''),
                    'category': project_data.get('projectCategory', {}).get('name', ''),
                    'avatar_url': project_data.get('avatarUrls', {}).get('48x48', '')
                }

            return None

        except Exception as e:
            logger.error(f"Ошибка получения информации о проекте: {e}")
            return None


# Создаем глобальный экземпляр
jira_integration = JiraIntegration()