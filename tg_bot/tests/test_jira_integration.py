"""
Комплексный тест интеграции с Jira API
Выводит всех пользователей, все проекты и все задачи
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import config
from services.jira_integration import JiraIntegration
import requests
from datetime import datetime
import json


class JiraDataExporter:
    """Экспорт всех данных из Jira"""

    def __init__(self):
        print("=" * 80)
        print("ЭКСПОРТ ВСЕХ ДАННЫХ ИЗ JIRA")
        print("=" * 80)

        # Выводим информацию о конфигурации
        print("\n1. ПРОВЕРКА КОНФИГУРАЦИИ:")
        print("-" * 40)
        print(f"JIRA_URL: {config.JIRA_URL}")
        print(f"JIRA_EMAIL: {config.JIRA_EMAIL}")
        print(f"JIRA_API_TOKEN длина: {len(config.JIRA_API_TOKEN)} символов")

        # Создаем экземпляр интеграции
        self.jira = JiraIntegration()
        self.base_url = config.JIRA_URL
        self.auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def get_all_users(self, max_results=100):
        """Получение ВСЕХ пользователей"""
        print(f"\n\n{'='*60}")
        print("ВСЕ ПОЛЬЗОВАТЕЛИ JIRA")
        print(f"{'='*60}")

        try:
            url = f"{self.base_url}/rest/api/3/users/search"

            params = {
                'maxResults': max_results,
                'startAt': 0
            }

            all_users = []

            while True:
                response = requests.get(
                    url,
                    headers=self.headers,
                    auth=self.auth,
                    params=params,
                    timeout=10
                )

                if response.status_code == 200:
                    users = response.json()
                    if not users:  # Больше нет пользователей
                        break

                    all_users.extend(users)
                    print(f"Загружено пользователей: {len(users)} (всего: {len(all_users)})")

                    # Если получено меньше запрошенного количества, значит это последняя страница
                    if len(users) < max_results:
                        break

                    params['startAt'] += max_results
                else:
                    print(f"❌ Ошибка получения пользователей: {response.status_code}")
                    print(f"Ответ: {response.text[:200]}")
                    break

            print(f"\n✅ Всего пользователей найдено: {len(all_users)}")

            # Выводим всех пользователей
            for i, user in enumerate(all_users, 1):
                print(f"\n{i:3}. {user.get('displayName', 'Без имени')}")
                print(f"    Account ID: {user.get('accountId', 'N/A')}")
                print(f"    Email: {user.get('emailAddress', 'N/A')}")
                print(f"    Активный: {'Да' if user.get('active', False) else 'Нет'}")
                print(f"    Time Zone: {user.get('timeZone', 'N/A')}")

            return all_users

        except Exception as e:
            print(f"❌ Исключение при получении пользователей: {e}")
            return []

    @property
    def get_all_projects(self):
        """Получение ВСЕХ проектов"""
        print(f"\n\n{'='*60}")
        print("ВСЕ ПРОЕКТЫ JIRA")
        print(f"{'='*60}")

        try:
            url = f"{self.base_url}/rest/api/3/project/search"

            params = {
                'maxResults': 100,
                'expand': 'description,lead,url,projectKeys'
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
                projects = data.get('values', [])
                print(f"✅ Всего проектов найдено: {len(projects)}")

                # Выводим все проекты
                for i, project in enumerate(projects, 1):
                    print(f"\n{i:3}. {project['key']} - {project['name']}")
                    print(f"    ID: {project.get('id', 'N/A')}")
                    print(f"    Тип: {project.get('projectTypeKey', 'N/A')}")
                    print(f"    Руководитель: {project.get('lead', {}).get('displayName', 'N/A')}")
                    print(f"    Описание: {project.get('description', 'Нет описания')[:100]}...")

                    # Получаем все задачи проекта
                    self.get_all_project_issues(project['key'])

                return projects
            else:
                print(f"❌ Ошибка получения проектов: {response.status_code}")
                print(f"Ответ: {response.text[:200]}")
                return []

        except Exception as e:
            print(f"❌ Исключение при получении проектов: {e}")
            return []

    async def get_all_project_issues(self, project_key, max_issues=500):
        """Получение ВСЕХ задач проекта"""
        print(f"\n    {'-'*50}")
        print(f"    ЗАДАЧИ ПРОЕКТА: {project_key}")
        print(f"    {'-'*50}")

        try:
            url = f"{self.base_url}/rest/api/3/search/jql"

            # JQL для получения всех задач проекта
            jql = f'project = {project_key} ORDER BY created DESC'

            all_issues = []
            start_at = 0
            max_results = 100  # Максимальное количество за один запрос

            while True:
                payload = {
                    'jql': jql,
                    'maxResults': max_results,
                    'startAt': start_at,
                    'fields': ['key', 'summary', 'status', 'assignee', 'creator',
                              'created', 'updated', 'priority', 'issuetype', 'sprint']
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

                    if not issues:
                        break

                    all_issues.extend(issues)

                    print(f"    Загружено задач: {len(issues)} (всего: {len(all_issues)} из {total})")

                    # Если достигли лимита или получили все задачи
                    if len(issues) < max_results or len(all_issues) >= max_issues:
                        break

                    start_at += max_results
                else:
                    print(f"    ❌ Ошибка получения задач: {response.status_code}")
                    print(f"    Ответ: {response.text[:100]}")
                    break

            # Выводим все задачи проекта
            print(f"\n    📋 Всего задач в проекте {project_key}: {len(all_issues)}")

            for i, issue in enumerate(all_issues[:50], 1):  # Выводим первые 50 задач
                fields = issue.get('fields', {})
                print(f"\n    {i:3}. {issue.get('key')}")
                print(f"        Название: {fields.get('summary', 'Без названия')[:80]}...")
                print(f"        Тип: {fields.get('issuetype', {}).get('name', 'N/A')}")
                print(f"        Статус: {fields.get('status', {}).get('name', 'N/A')}")

                assignee = fields.get('assignee')
                if assignee:
                    print(f"        Исполнитель: {assignee.get('displayName', 'N/A')}")
                else:
                    print(f"        Исполнитель: Не назначен")

                created = fields.get('created')
                if created:
                    created_date = self._parse_jira_date(created)
                    print(f"        Создана: {created_date}")

            if len(all_issues) > 50:
                print(f"\n    ... и еще {len(all_issues) - 50} задач")

            return all_issues

        except Exception as e:
            print(f"    ❌ Исключение при получении задач: {e}")
            return []

    def get_all_boards(self):
        """Получение ВСЕХ досок"""
        print(f"\n\n{'='*60}")
        print("ВСЕ ДОСКИ JIRA")
        print(f"{'='*60}")

        try:
            url = f"{self.base_url}/rest/agile/1.0/board"

            params = {
                'maxResults': 100,
                'startAt': 0
            }

            all_boards = []

            while True:
                response = requests.get(
                    url,
                    headers=self.headers,
                    auth=self.auth,
                    params=params,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    boards = data.get('values', [])

                    if not boards:
                        break

                    all_boards.extend(boards)
                    print(f"Загружено досок: {len(boards)} (всего: {len(all_boards)})")

                    params['startAt'] += len(boards)

                    # Если это последняя страница
                    if len(boards) < params['maxResults']:
                        break
                else:
                    print(f"❌ Ошибка получения досок: {response.status_code}")
                    break

            print(f"\n✅ Всего досок найдено: {len(all_boards)}")

            for i, board in enumerate(all_boards, 1):
                print(f"\n{i:3}. {board.get('name', 'Без названия')}")
                print(f"    ID: {board.get('id', 'N/A')}")
                print(f"    Тип: {board.get('type', 'N/A')}")
                print(f"    Проект: {board.get('location', {}).get('projectName', 'N/A')}")

            return all_boards

        except Exception as e:
            print(f"❌ Исключение при получении досок: {e}")
            return []

    def get_all_sprints(self):
        """Получение ВСЕХ спринтов со ВСЕХ досок"""
        print(f"\n\n{'='*60}")
        print("ВСЕ СПРИНТЫ JIRA")
        print(f"{'='*60}")

        try:
            # Сначала получаем все доски
            boards = self.get_all_boards()

            if not boards:
                print("Нет досок для получения спринтов")
                return []

            all_sprints = []

            for board in boards:
                board_id = board.get('id')
                board_name = board.get('name')

                print(f"\n📋 Доска: {board_name} (ID: {board_id})")

                url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint"

                response = requests.get(
                    url,
                    headers=self.headers,
                    auth=self.auth,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    sprints = data.get('values', [])

                    if sprints:
                        all_sprints.extend(sprints)
                        print(f"  Найдено спринтов: {len(sprints)}")

                        for sprint in sprints[:10]:  # Выводим первые 10 спринтов
                            print(f"    • {sprint.get('name')} ({sprint.get('state', 'unknown')})")

                        if len(sprints) > 10:
                            print(f"    ... и еще {len(sprints) - 10} спринтов")
                    else:
                        print(f"  На этой доске нет спринтов")
                else:
                    print(f"  ❌ Ошибка получения спринтов: {response.status_code}")

            print(f"\n✅ Всего спринтов найдено: {len(all_sprints)}")

            # Группируем спринты по состоянию
            active_sprints = [s for s in all_sprints if s.get('state') == 'active']
            future_sprints = [s for s in all_sprints if s.get('state') == 'future']
            closed_sprints = [s for s in all_sprints if s.get('state') == 'closed']

            print(f"\n📊 Статистика по спринтам:")
            print(f"   Активных: {len(active_sprints)}")
            print(f"   Будущих: {len(future_sprints)}")
            print(f"   Завершенных: {len(closed_sprints)}")

            return all_sprints

        except Exception as e:
            print(f"❌ Исключение при получении спринтов: {e}")
            return []

    def get_system_info(self):
        """Получение информации о системе Jira"""
        print(f"\n\n{'='*60}")
        print("ИНФОРМАЦИЯ О СИСТЕМЕ JIRA")
        print(f"{'='*60}")

        try:
            # Информация о сервере
            url = f"{self.base_url}/rest/api/3/serverInfo"

            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                timeout=10
            )

            if response.status_code == 200:
                server_info = response.json()
                print(f"✅ Информация о сервере:")
                print(f"   Версия: {server_info.get('version')}")
                print(f"   Номер сборки: {server_info.get('buildNumber')}")
                print(f"   Дата сборки: {server_info.get('buildDate')}")
                print(f"   Время сервера: {server_info.get('serverTime')}")
                print(f"   Название: {server_info.get('serverTitle')}")
                print(f"   URL: {server_info.get('baseUrl')}")

            # Информация о пользователе
            url = f"{self.base_url}/rest/api/3/myself"

            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                timeout=10
            )

            if response.status_code == 200:
                user_info = response.json()
                print(f"\n✅ Информация о текущем пользователе:")
                print(f"   Имя: {user_info.get('displayName')}")
                print(f"   Account ID: {user_info.get('accountId')}")
                print(f"   Email: {user_info.get('emailAddress')}")
                print(f"   Time Zone: {user_info.get('timeZone')}")

        except Exception as e:
            print(f"❌ Исключение при получении информации о системе: {e}")

    def _parse_jira_date(self, date_str):
        """Парсинг даты из формата Jira"""
        if not date_str:
            return "N/A"

        try:
            # Пробуем разные форматы дат
            formats = [
                '%Y-%m-%dT%H:%M:%S.%f%z',
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d'
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%d.%m.%Y %H:%M:%S')
                except ValueError:
                    continue

            return date_str  # Возвращаем как есть если не удалось распарсить

        except Exception:
            return date_str

    def export_all_data(self):
        """Экспорт всех данных из Jira"""
        print("\n" + "=" * 80)
        print("НАЧАЛО ЭКСПОРТА ВСЕХ ДАННЫХ ИЗ JIRA")
        print("=" * 80)

        # Сохраняем все данные в словарь
        all_data = {
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'jira_url': self.base_url,
            'jira_email': config.JIRA_EMAIL,
            'system_info': {},
            'users': [],
            'projects': [],
            'boards': [],
            'sprints': [],
            'issues_by_project': {}
        }

        try:
            # 1. Информация о системе
            self.get_system_info()

            # 2. Все пользователи
            all_data['users'] = self.get_all_users()

            # 3. Все проекты
            all_data['projects'] = self.get_all_projects

            # 4. Все доски
            all_data['boards'] = self.get_all_boards()

            # 5. Все спринты
            all_data['sprints'] = self.get_all_sprints()

            print("\n" + "=" * 80)
            print("✅ ЭКСПОРТ ДАННЫХ ЗАВЕРШЕН УСПЕШНО!")
            print("=" * 80)

            # Сохраняем результаты в файл
            self.save_results_to_file(all_data)

            return all_data

        except Exception as e:
            print(f"\n❌ Ошибка при экспорте данных: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_results_to_file(self, data):
        """Сохранение результатов в файлы"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Сохраняем в JSON
            json_filename = f"jira_export_{timestamp}.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            # Сохраняем в текстовый файл
            txt_filename = f"jira_export_{timestamp}.txt"
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("ЭКСПОРТ ДАННЫХ ИЗ JIRA\n")
                f.write("=" * 80 + "\n\n")

                f.write(f"Дата экспорта: {data['export_date']}\n")
                f.write(f"Jira URL: {data['jira_url']}\n")
                f.write(f"Аккаунт: {data['jira_email']}\n\n")

                f.write(f"Всего пользователей: {len(data['users'])}\n")
                f.write(f"Всего проектов: {len(data['projects'])}\n")
                f.write(f"Всего досок: {len(data['boards'])}\n")
                f.write(f"Всего спринтов: {len(data['sprints'])}\n\n")

                f.write("ПОЛЬЗОВАТЕЛИ:\n")
                f.write("-" * 40 + "\n")
                for user in data['users'][:100]:  # Первые 100 пользователей
                    f.write(f"• {user.get('displayName', 'Без имени')}\n")
                    f.write(f"  Email: {user.get('emailAddress', 'N/A')}\n")
                    f.write(f"  Account ID: {user.get('accountId', 'N/A')}\n\n")

                f.write("\nПРОЕКТЫ:\n")
                f.write("-" * 40 + "\n")
                for project in data['projects']:
                    f.write(f"• {project['key']} - {project['name']}\n")
                    f.write(f"  ID: {project.get('id', 'N/A')}\n")
                    f.write(f"  Руководитель: {project.get('lead', {}).get('displayName', 'N/A')}\n\n")

            print(f"\n📄 Результаты сохранены в файлы:")
            print(f"   • JSON: {json_filename}")
            print(f"   • TXT: {txt_filename}")

        except Exception as e:
            print(f"❌ Ошибка сохранения результатов: {e}")


async def main():
    """Основная функция запуска экспорта"""

    print("\nПАРАМЕТРЫ ЭКСПОРТА:")
    print(f"Корпоративный аккаунт: {config.JIRA_EMAIL}")
    print(f"Jira URL: {config.JIRA_URL}")

    # Запрашиваем подтверждение
    response = input("\nЗапустить экспорт ВСЕХ данных из Jira? (y/n): ").strip().lower()

    if response != 'y':
        print("Экспорт отменен.")
        return

    # Запускаем экспорт
    exporter = JiraDataExporter()

    # Запускаем экспорт всех данных
    all_data = exporter.export_all_data()

    if all_data:
        print(f"\n📊 СВОДКА ЭКСПОРТИРОВАННЫХ ДАННЫХ:")
        print(f"   • Пользователей: {len(all_data['users'])}")
        print(f"   • Проектов: {len(all_data['projects'])}")
        print(f"   • Досок: {len(all_data['boards'])}")
        print(f"   • Спринтов: {len(all_data['sprints'])}")

        # Подсчитываем общее количество задач
        total_issues = 0
        for project_key, issues in all_data['issues_by_project'].items():
            total_issues += len(issues)

        print(f"   • Задач (оценка): {total_issues}")

    print("\n" + "=" * 80)
    print("ЭКСПОРТ ЗАВЕРШЕН!")
    print("=" * 80)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nЭкспорт прерван пользователем.")
    except Exception as e:
        print(f"\n❌ Непредвиденная ошибка: {e}")
        import traceback
        traceback.print_exc()