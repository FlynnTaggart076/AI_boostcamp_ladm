# test_find_user_jira_fixed.py
"""
Тестовый файл для поиска пользователя Jira по имени
и вывода всех его задач, спринтов и проектов
С исправленными эндпоинтами /jql и раздельными спринтами
"""
import requests
from config.settings import config
import json
from datetime import datetime


class JiraUserDataFinder:
    def __init__(self):
        self.base_url = config.JIRA_URL
        self.auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        # Имя пользователя для поиска (можно изменить)
        self.target_user_name = "Ильичева Кристина"  # ИЗМЕНИТЕ ЭТО ИМЯ НА НУЖНОЕ

        print("=" * 80)
        print(f"ПОИСК ДАННЫХ ПОЛЬЗОВАТЕЛЯ JIRA: {self.target_user_name}")
        print("=" * 80)

    def find_user_by_name(self):
        """Поиск пользователя по имени (displayName)"""
        print("\n1. 🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ ПО ИМЕНИ...")
        print("-" * 60)

        try:
            url = f"{self.base_url}/rest/api/3/user/search"

            params = {
                'query': self.target_user_name,
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

                if not users:
                    print("❌ Пользователь не найден!")
                    print(f"Имя для поиска: {self.target_user_name}")
                    print("Возможные причины:")
                    print("1. Неверное имя пользователя")
                    print("2. Пользователь неактивен в Jira")
                    print("3. У вас нет прав на просмотр этого пользователя")
                    return None

                # Ищем точное совпадение
                exact_match = None
                for user in users:
                    if user.get('displayName', '').lower() == self.target_user_name.lower():
                        exact_match = user
                        break

                # Если нет точного совпадения, берем первого
                if not exact_match and users:
                    print(f"⚠️  Точного совпадения не найдено. Используется первый результат:")
                    exact_match = users[0]

                if exact_match:
                    user_info = {
                        'account_id': exact_match.get('accountId'),
                        'display_name': exact_match.get('displayName'),
                        'email_address': exact_match.get('emailAddress'),
                        'active': exact_match.get('active', False),
                        'time_zone': exact_match.get('timeZone', 'N/A'),
                        'avatar_url': exact_match.get('avatarUrls', {}).get('48x48', '')
                    }

                    print(f"✅ ПОЛЬЗОВАТЕЛЬ НАЙДЕН:")
                    print(f"   Имя: {user_info['display_name']}")
                    print(f"   Account ID: {user_info['account_id']}")
                    print(f"   Email: {user_info['email_address']}")
                    print(f"   Активен: {'Да' if user_info['active'] else 'Нет'}")
                    print(f"   Часовой пояс: {user_info['time_zone']}")

                    return user_info

            else:
                print(f"❌ Ошибка поиска пользователя: {response.status_code}")
                print(f"Ответ: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"❌ Исключение при поиске пользователя: {e}")
            return None

    def get_user_projects_and_issues(self, account_id):
        """Получение проектов и задач пользователя"""
        print(f"\n2. 📊 ПРОЕКТЫ И ЗАДАЧИ ПОЛЬЗОВАТЕЛЯ")
        print("-" * 60)

        try:
            url = f"{self.base_url}/rest/api/3/search/jql"  # С /jql

            # JQL запрос для получения всех задач пользователя
            jql = f'assignee = "{account_id}" ORDER BY created DESC'

            payload = {
                'jql': jql,
                'maxResults': 100,
                'fields': [
                    'key', 'summary', 'project', 'status', 'assignee',
                    'created', 'updated', 'priority', 'issuetype', 'sprint'
                ]
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
                total_issues = data.get('total', 0)

                print(f"✅ Всего задач найдено: {total_issues}")

                if not issues:
                    print("У пользователя нет задач")
                    return {}

                # Группируем задачи по проектам
                projects_dict = {}

                for issue in issues:
                    project_data = issue['fields']['project']
                    project_key = project_data['key']

                    if project_key not in projects_dict:
                        projects_dict[project_key] = {
                            'key': project_key,
                            'name': project_data['name'],
                            'id': project_data['id'],
                            'avatar_url': project_data.get('avatarUrls', {}).get('48x48', ''),
                            'issues': []
                        }

                    # Извлекаем информацию о задаче
                    fields = issue['fields']

                    # Обрабатываем спринт
                    sprint_info = None
                    sprint_data = fields.get('sprint')
                    if sprint_data:
                        if isinstance(sprint_data, list) and sprint_data:
                            sprint_info = sprint_data[0]
                        elif isinstance(sprint_data, dict):
                            sprint_info = sprint_data

                    task_info = {
                        'key': issue['key'],
                        'summary': fields.get('summary', 'Без названия'),
                        'status': fields.get('status', {}).get('name', 'N/A'),
                        'priority': fields.get('priority', {}).get('name', 'N/A'),
                        'issue_type': fields.get('issuetype', {}).get('name', 'N/A'),
                        'created': self._parse_date(fields.get('created')),
                        'updated': self._parse_date(fields.get('updated')),
                        'sprint': sprint_info
                    }

                    projects_dict[project_key]['issues'].append(task_info)

                # Выводим проекты и задачи
                for project_key, project_data in projects_dict.items():
                    print(f"\n   📁 ПРОЕКТ: {project_key} - {project_data['name']}")
                    print(f"      ID проекта: {project_data['id']}")
                    print(f"      Задач в проекте: {len(project_data['issues'])}")

                    # Выводим задачи
                    for i, task in enumerate(project_data['issues'][:20], 1):  # Первые 20 задач
                        print(f"\n      {i:2}. {task['key']}: {task['summary'][:80]}...")
                        print(f"          Статус: {task['status']}")
                        print(f"          Приоритет: {task['priority']}")
                        print(f"          Тип: {task['issue_type']}")

                        if task['sprint']:
                            sprint_state = task['sprint'].get('state', 'unknown')
                            state_emoji = '🟢' if sprint_state == 'active' else '🔵' if sprint_state == 'future' else '⚫'
                            print(f"          Спринт: {task['sprint'].get('name', 'N/A')} {state_emoji}")
                            print(f"          Состояние спринта: {sprint_state}")

                        print(f"          Создана: {task['created']}")
                        print(f"          Обновлена: {task['updated']}")

                    if len(project_data['issues']) > 20:
                        print(f"      ... и еще {len(project_data['issues']) - 20} задач")

                return projects_dict

            else:
                print(f"❌ Ошибка получения задач: {response.status_code}")
                print(f"Ответ: {response.text[:200]}")
                return {}

        except Exception as e:
            print(f"❌ Исключение при получении задач: {e}")
            return {}

    def get_project_sprints(self, project_key):
        """Получение спринтов проекта - раздельно текущие и будущие"""
        print(f"\n3. 🏃 СПРИНТЫ ПРОЕКТА {project_key}")
        print("-" * 60)

        try:
            # Ищем доски проекта
            url = f"{self.base_url}/rest/agile/1.0/board"

            params = {
                'type': 'scrum',
                'projectKeyOrId': project_key,
                'maxResults': 10
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

                if not boards:
                    print(f"   ❌ Нет досок для проекта {project_key}")
                    return {'active': [], 'future': [], 'closed': []}

                active_sprints = []
                future_sprints = []
                closed_sprints = []

                for board in boards:
                    board_id = board['id']
                    board_name = board['name']

                    print(f"   📋 Доска: {board_name} (ID: {board_id})")

                    # Получаем спринты доски
                    sprints_url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint"

                    sprints_response = requests.get(
                        sprints_url,
                        headers=self.headers,
                        auth=self.auth,
                        timeout=10
                    )

                    if sprints_response.status_code == 200:
                        sprints_data = sprints_response.json()
                        sprints = sprints_data.get('values', [])

                        if sprints:
                            # Разделяем спринты по состоянию
                            for sprint in sprints:
                                state = sprint.get('state', 'unknown')
                                if state == 'active':
                                    active_sprints.append(sprint)
                                elif state == 'future':
                                    future_sprints.append(sprint)
                                elif state == 'closed':
                                    closed_sprints.append(sprint)

                    else:
                        print(f"      ❌ Ошибка получения спринтов: {sprints_response.status_code}")

                # Выводим ТЕКУЩИЕ спринты
                print(f"\n   🟢 АКТИВНЫЕ (ТЕКУЩИЕ) СПРИНТЫ: {len(active_sprints)}")
                if active_sprints:
                    for sprint in active_sprints:
                        print(f"\n      • {sprint['name']}")
                        print(f"        ID: {sprint['id']}")
                        if sprint.get('startDate'):
                            print(f"        Начало: {self._parse_date(sprint['startDate'])}")
                        if sprint.get('endDate'):
                            print(f"        Конец: {self._parse_date(sprint['endDate'])}")
                        if sprint.get('goal'):
                            print(f"        Цель: {sprint['goal'][:100]}...")
                else:
                    print(f"      Нет активных спринтов")

                # Выводим БУДУЩИЕ спринты
                print(f"\n   🔵 БУДУЩИЕ СПРИНТЫ: {len(future_sprints)}")
                if future_sprints:
                    for sprint in future_sprints:
                        print(f"\n      • {sprint['name']}")
                        print(f"        ID: {sprint['id']}")
                        if sprint.get('startDate'):
                            print(f"        Начало: {self._parse_date(sprint['startDate'])}")
                        if sprint.get('endDate'):
                            print(f"        Конец: {self._parse_date(sprint['endDate'])}")
                else:
                    print(f"      Нет будущих спринтов")

                # Выводим ЗАКРЫТЫЕ спринты (кратко)
                print(f"\n   ⚫ ЗАКРЫТЫЕ СПРИНТЫ: {len(closed_sprints)}")
                if closed_sprints:
                    # Показываем только последние 5 закрытых спринтов
                    recent_closed = closed_sprints[-5:] if len(closed_sprints) > 5 else closed_sprints
                    for sprint in recent_closed:
                        print(f"      • {sprint['name']}")
                    if len(closed_sprints) > 5:
                        print(f"      ... и еще {len(closed_sprints) - 5} закрытых спринтов")

                return {
                    'active': active_sprints,
                    'future': future_sprints,
                    'closed': closed_sprints
                }

            else:
                print(f"   ❌ Ошибка получения досок: {response.status_code}")
                return {'active': [], 'future': [], 'closed': []}

        except Exception as e:
            print(f"   ❌ Исключение при получении спринтов: {e}")
            return {'active': [], 'future': [], 'closed': []}

    def get_all_projects_for_user(self, account_id):
        """Получение всех проектов, в которых есть пользователь"""
        print(f"\n4. 🏢 ВСЕ ПРОЕКТЫ С УЧАСТИЕМ ПОЛЬЗОВАТЕЛЯ")
        print("-" * 60)

        try:
            # Получаем все проекты
            url = f"{self.base_url}/rest/api/3/project/search"

            params = {
                'maxResults': 100,
                'expand': 'description,lead'
            }

            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                all_projects = data.get('values', [])

                print(f"   Всего проектов в Jira: {len(all_projects)}")

                # Для каждого проекта проверяем, есть ли у пользователя задачи
                user_projects = []

                for project in all_projects:
                    project_key = project['key']

                    # Проверяем, есть ли задачи у пользователя в этом проекте
                    check_url = f"{self.base_url}/rest/api/3/search/jql"  # С /jql

                    check_payload = {
                        'jql': f'project = {project_key} AND assignee = "{account_id}"',
                        'maxResults': 1,
                        'fields': ['key']
                    }

                    check_response = requests.post(
                        check_url,
                        headers=self.headers,
                        auth=self.auth,
                        json=check_payload,
                        timeout=5
                    )

                    if check_response.status_code == 200:
                        check_data = check_response.json()
                        if check_data.get('total', 0) > 0:
                            user_projects.append(project)

                print(f"   Проектов с участием пользователя: {len(user_projects)}")

                # Выводим проекты
                for i, project in enumerate(user_projects, 1):
                    print(f"\n   {i:2}. {project['key']} - {project['name']}")
                    print(f"       ID: {project.get('id', 'N/A')}")
                    print(f"       Руководитель: {project.get('lead', {}).get('displayName', 'N/A')}")

                    description = project.get('description', 'Нет описания')
                    if description and len(description) > 100:
                        description = description[:100] + "..."
                    print(f"       Описание: {description}")

                return user_projects

            else:
                print(f"   ❌ Ошибка получения проектов: {response.status_code}")
                return []

        except Exception as e:
            print(f"   ❌ Исключение при получении проектов: {e}")
            return []

    def get_user_sprint_tasks(self, account_id, sprint_state='active'):
        """Получение задач пользователя в спринтах по состоянию"""
        state_names = {
            'active': 'АКТИВНЫХ',
            'future': 'БУДУЩИХ',
            'closed': 'ЗАКРЫТЫХ'
        }

        print(f"\n5. 🎯 ЗАДАЧИ В {state_names.get(sprint_state, sprint_state.upper())} СПРИНТАХ")
        print("-" * 60)

        try:
            url = f"{self.base_url}/rest/api/3/search/jql"  # С /jql

            # JQL для задач в спринтах определенного состояния
            if sprint_state == 'active':
                jql = f'assignee = "{account_id}" AND sprint in openSprints()'
            elif sprint_state == 'future':
                jql = f'assignee = "{account_id}" AND sprint IS NOT EMPTY AND sprint NOT in openSprints() AND sprint NOT in closedSprints()'
            else:  # closed
                jql = f'assignee = "{account_id}" AND sprint in closedSprints()'

            payload = {
                'jql': jql,
                'maxResults': 100,
                'fields': [
                    'key', 'summary', 'project', 'status', 'sprint',
                    'priority', 'issuetype', 'created', 'updated'
                ]
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
                total = data.get('total', 0)

                print(f"   Задач в {state_names.get(sprint_state, sprint_state).lower()} спринтах: {total}")

                if not issues:
                    print(
                        f"   У пользователя нет задач в {state_names.get(sprint_state, sprint_state).lower()} спринтах")
                    return {}

                # Группируем по спринтам
                sprints_dict = {}

                for issue in issues:
                    sprint_data = issue['fields'].get('sprint')

                    if not sprint_data:
                        sprint_key = 'Без спринта'
                    else:
                        if isinstance(sprint_data, list) and sprint_data:
                            sprint = sprint_data[0]
                        elif isinstance(sprint_data, dict):
                            sprint = sprint_data
                        else:
                            sprint_key = 'Неизвестный спринт'
                            sprint = {}

                        sprint_key = sprint.get('name', 'Неизвестный спринт')
                        sprint_id = sprint.get('id')
                        sprint_state_actual = sprint.get('state', sprint_state)

                        if sprint_key not in sprints_dict:
                            sprints_dict[sprint_key] = {
                                'id': sprint_id,
                                'state': sprint_state_actual,
                                'start_date': self._parse_date(sprint.get('startDate')),
                                'end_date': self._parse_date(sprint.get('endDate')),
                                'complete_date': self._parse_date(sprint.get('completeDate')),
                                'issues': []
                            }

                    task_info = {
                        'key': issue['key'],
                        'summary': issue['fields'].get('summary', 'Без названия'),
                        'project': issue['fields']['project']['key'],
                        'project_name': issue['fields']['project']['name'],
                        'status': issue['fields'].get('status', {}).get('name', 'N/A'),
                        'priority': issue['fields'].get('priority', {}).get('name', 'N/A'),
                        'issue_type': issue['fields'].get('issuetype', {}).get('name', 'N/A'),
                        'created': self._parse_date(issue['fields'].get('created')),
                        'updated': self._parse_date(issue['fields'].get('updated'))
                    }

                    sprints_dict[sprint_key]['issues'].append(task_info)

                # Выводим задачи по спринтам
                for sprint_name, sprint_data in sprints_dict.items():
                    state_emoji = '🟢' if sprint_data['state'] == 'active' else '🔵' if sprint_data[
                                                                                          'state'] == 'future' else '⚫'
                    print(f"\n   {state_emoji} СПРИНТ: {sprint_name}")
                    print(f"      Состояние: {sprint_data['state']}")
                    if sprint_data['start_date']:
                        print(f"      Начало: {sprint_data['start_date']}")
                    if sprint_data['end_date']:
                        print(f"      Конец: {sprint_data['end_date']}")
                    if sprint_data['complete_date'] and sprint_data['state'] == 'closed':
                        print(f"      Завершен: {sprint_data['complete_date']}")
                    print(f"      Задач: {len(sprint_data['issues'])}")

                    for task in sprint_data['issues']:
                        print(f"\n      • {task['key']} [{task['project']}]")
                        print(f"        {task['summary'][:80]}...")
                        print(f"        Статус: {task['status']}")
                        print(f"        Приоритет: {task['priority']}")
                        print(f"        Тип: {task['issue_type']}")
                        print(f"        Проект: {task['project_name']}")
                        print(f"        Обновлена: {task['updated']}")

                return sprints_dict

            else:
                print(f"   ❌ Ошибка получения задач спринта: {response.status_code}")
                return {}

        except Exception as e:
            print(f"   ❌ Исключение при получении задач спринта: {e}")
            return {}

    def get_current_and_future_sprint_tasks(self, account_id):
        """Получение задач пользователя в текущих и будущих спринтах"""
        print(f"\n5. 🎯 ЗАДАЧИ В СПРИНТАХ")
        print("-" * 60)

        # Текущие спринты
        print(f"\n   🟢 ЗАДАЧИ В АКТИВНЫХ СПРИНТАХ:")
        active_sprint_tasks = self.get_user_sprint_tasks(account_id, 'active')

        # Будущие спринты
        print(f"\n   🔵 ЗАДАЧИ В БУДУЩИХ СПРИНТАХ:")
        future_sprint_tasks = self.get_user_sprint_tasks(account_id, 'future')

        # Закрытые спринты (по желанию)
        print(f"\n   ⚫ ЗАДАЧИ В ЗАКРЫТЫХ СПРИНТАХ (последние):")
        closed_sprint_tasks = self.get_user_sprint_tasks(account_id, 'closed')

        return {
            'active': active_sprint_tasks,
            'future': future_sprint_tasks,
            'closed': closed_sprint_tasks
        }

    def get_current_tasks(self, account_id):
        """Получение текущих задач (не в спринтах или в активных)"""
        print(f"\n6. 📝 ТЕКУЩИЕ ЗАДАЧИ (НЕ В СПРИНТАХ)")
        print("-" * 60)

        try:
            url = f"{self.base_url}/rest/api/3/search/jql"  # С /jql

            # JQL для задач без спринта или в активных спринтах
            jql = f'assignee = "{account_id}" AND (sprint IS EMPTY OR sprint in openSprints())'

            payload = {
                'jql': jql,
                'maxResults': 50,
                'fields': [
                    'key', 'summary', 'project', 'status', 'sprint',
                    'priority', 'issuetype', 'created', 'updated'
                ]
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
                total = data.get('total', 0)

                print(f"   Всего текущих задач: {total}")

                if not issues:
                    print("   Нет текущих задач")
                    return []

                tasks_without_sprint = []
                tasks_with_active_sprint = []

                for issue in issues:
                    sprint_data = issue['fields'].get('sprint')
                    has_sprint = sprint_data is not None

                    task_info = {
                        'key': issue['key'],
                        'summary': issue['fields'].get('summary', 'Без названия'),
                        'project': issue['fields']['project']['key'],
                        'status': issue['fields'].get('status', {}).get('name', 'N/A'),
                        'priority': issue['fields'].get('priority', {}).get('name', 'N/A'),
                        'has_sprint': has_sprint,
                        'sprint_name': None
                    }

                    if has_sprint:
                        if isinstance(sprint_data, list) and sprint_data:
                            task_info['sprint_name'] = sprint_data[0].get('name', 'Неизвестно')
                            tasks_with_active_sprint.append(task_info)
                        elif isinstance(sprint_data, dict):
                            task_info['sprint_name'] = sprint_data.get('name', 'Неизвестно')
                            tasks_with_active_sprint.append(task_info)
                    else:
                        tasks_without_sprint.append(task_info)

                # Выводим задачи без спринта
                print(f"\n   📋 ЗАДАЧИ БЕЗ СПРИНТА: {len(tasks_without_sprint)}")
                for task in tasks_without_sprint:
                    print(f"\n      • {task['key']} [{task['project']}]")
                    print(f"        {task['summary'][:80]}...")
                    print(f"        Статус: {task['status']}")
                    print(f"        Приоритет: {task['priority']}")

                # Выводим задачи в активных спринтах (кратко)
                print(f"\n   🏃 ЗАДАЧИ В АКТИВНЫХ СПРИНТАХ: {len(tasks_with_active_sprint)}")
                for task in tasks_with_active_sprint[:10]:  # Первые 10
                    print(f"      • {task['key']}: {task['summary'][:50]}...")

                return tasks_without_sprint + tasks_with_active_sprint

            else:
                print(f"   ❌ Ошибка получения текущих задач: {response.status_code}")
                return []

        except Exception as e:
            print(f"   ❌ Исключение при получении текущих задач: {e}")
            return []

    def get_future_tasks(self, account_id):
        """Получение будущих задач (в будущих спринтах)"""
        print(f"\n7. 🔮 БУДУЩИЕ ЗАДАЧИ (В БУДУЩИХ СПРИНТАХ)")
        print("-" * 60)

        try:
            url = f"{self.base_url}/rest/api/3/search/jql"  # С /jql

            # JQL для задач в будущих спринтах
            jql = f'assignee = "{account_id}" AND sprint IS NOT EMPTY AND sprint NOT in openSprints() AND sprint NOT in closedSprints()'

            payload = {
                'jql': jql,
                'maxResults': 30,
                'fields': [
                    'key', 'summary', 'project', 'status', 'sprint',
                    'priority', 'issuetype', 'created'
                ]
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
                total = data.get('total', 0)

                print(f"   Будущих задач: {total}")

                if not issues:
                    print("   Нет задач в будущих спринтах")
                    return []

                # Группируем по спринтам
                future_sprints = {}

                for issue in issues:
                    sprint_data = issue['fields'].get('sprint')

                    if sprint_data:
                        if isinstance(sprint_data, list) and sprint_data:
                            sprint = sprint_data[0]
                        elif isinstance(sprint_data, dict):
                            sprint = sprint_data
                        else:
                            continue

                        sprint_name = sprint.get('name', 'Неизвестный спринт')

                        if sprint_name not in future_sprints:
                            future_sprints[sprint_name] = {
                                'start_date': self._parse_date(sprint.get('startDate')),
                                'end_date': self._parse_date(sprint.get('endDate')),
                                'tasks': []
                            }

                        task_info = {
                            'key': issue['key'],
                            'summary': issue['fields'].get('summary', 'Без названия'),
                            'project': issue['fields']['project']['key'],
                            'status': issue['fields'].get('status', {}).get('name', 'N/A')
                        }

                        future_sprints[sprint_name]['tasks'].append(task_info)

                # Выводим будущие задачи
                for sprint_name, sprint_data in future_sprints.items():
                    print(f"\n   🔵 СПРИНТ: {sprint_name}")
                    if sprint_data['start_date']:
                        print(f"      Начало: {sprint_data['start_date']}")
                    if sprint_data['end_date']:
                        print(f"      Конец: {sprint_data['end_date']}")
                    print(f"      Задач: {len(sprint_data['tasks'])}")

                    for task in sprint_data['tasks']:
                        print(f"\n      • {task['key']} [{task['project']}]")
                        print(f"        {task['summary'][:80]}...")
                        print(f"        Статус: {task['status']}")

                return future_sprints

            else:
                print(f"   ❌ Ошибка получения будущих задач: {response.status_code}")
                return {}

        except Exception as e:
            print(f"   ❌ Исключение при получении будущих задач: {e}")
            return {}

    def _parse_date(self, date_str):
        """Парсинг даты из Jira формата"""
        if not date_str:
            return "N/A"

        try:
            # Убираем миллисекунды и временную зону для упрощения
            date_str = date_str.split('.')[0] if '.' in date_str else date_str
            date_str = date_str.replace('Z', '+00:00')

            dt = datetime.fromisoformat(date_str)
            return dt.strftime('%d.%m.%Y %H:%M')
        except:
            return date_str

    def run_full_analysis(self):
        """Запуск полного анализа пользователя"""
        print(f"\n{'=' * 80}")
        print(f"АНАЛИЗ ДАННЫХ ПОЛЬЗОВАТЕЛЯ: {self.target_user_name}")
        print(f"{'=' * 80}")

        # 1. Находим пользователя
        user_info = self.find_user_by_name()

        if not user_info:
            print("\n❌ Анализ завершен: пользователь не найден")
            return

        account_id = user_info['account_id']

        # 2. Получаем все проекты с участием пользователя
        self.get_all_projects_for_user(account_id)

        # 3. Получаем проекты и задачи
        projects_data = self.get_user_projects_and_issues(account_id)

        # 4. Для каждого проекта получаем спринты (раздельно)
        if projects_data:
            for project_key in projects_data.keys():
                self.get_project_sprints(project_key)

        # 5. Получаем задачи в спринтах (раздельно)
        self.get_current_and_future_sprint_tasks(account_id)

        # 6. Текущие задачи (не в спринтах)
        self.get_current_tasks(account_id)

        # 7. Будущие задачи (в будущих спринтах)
        self.get_future_tasks(account_id)

        print(f"\n{'=' * 80}")
        print(f"✅ АНАЛИЗ ЗАВЕРШЕН ДЛЯ: {user_info['display_name']}")
        print(f"📧 Email: {user_info['email_address']}")
        print(f"🆔 Account ID: {account_id}")
        print(f"{'=' * 80}")

        # Сохраняем результаты в файл
        self.save_results(user_info, projects_data)



def main():
    """Основная функция запуска"""
    print("JIRA USER DATA ANALYZER (с разделением спринтов)")
    print("=" * 50)

    # Создаем экземпляр анализатора
    analyzer = JiraUserDataFinder()

    # Запускаем полный анализ
    analyzer.run_full_analysis()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nАнализ прерван пользователем.")
    except Exception as e:
        print(f"\n❌ Непредвиденная ошибка: {e}")
        import traceback

        traceback.print_exc()