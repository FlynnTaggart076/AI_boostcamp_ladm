import logging
import requests
from typing import Dict, Optional, List
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
        """Поиск пользователя по имени"""
        try:
            url = f"{self.base_url}/rest/api/3/user/search"
            params = {'query': display_name, 'maxResults': 50}

            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                users = response.json()
                for user in users:
                    if user.get('displayName', '').lower() == display_name.lower():
                        return {
                            'account_id': user.get('accountId'),
                            'display_name': user.get('displayName'),
                            'email_address': user.get('emailAddress'),
                            'active': user.get('active', False)
                        }
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска пользователя Jira: {e}")
            return None

    def get_user_projects_by_account_id(self, account_id: str) -> List[Dict]:
        """Получение проектов пользователя по accountId"""
        try:
            url = f"{self.base_url}/rest/api/3/search/jql"
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

                    sprint_data = issue['fields'].get('sprint')
                    sprint_info = None

                    if sprint_data:
                        if isinstance(sprint_data, list) and sprint_data:
                            active_sprints = [s for s in sprint_data if s.get('state') == 'active']
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

                return list(projects.values())

            return []
        except Exception as e:
            logger.error(f"Ошибка получения проектов пользователя: {e}")
            return []


jira_integration = JiraIntegration()
