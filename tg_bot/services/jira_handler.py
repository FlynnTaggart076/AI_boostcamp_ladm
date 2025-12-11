"""
Обработчик Jira данных при регистрации пользователя
"""
import logging
from datetime import datetime
from services.jira_integration import jira_integration

logger = logging.getLogger(__name__)


def fetch_jira_user_data(user_id: int, jira_account: str, user_name: str):
    """
    Получение данных Jira для пользователя (без сохранения в БД)

    Args:
        user_id: ID пользователя в нашей системе
        jira_account: Ник пользователя в Jira (display name)
        user_name: Имя пользователя
    """
    print("=" * 60)
    print("НАЧАЛО СИНХРОНИЗАЦИИ С JIRA")
    print("=" * 60)
    print(f"Пользователь: {user_name}")
    print(f"Jira аккаунт для поиска: {jira_account}")
    print(f"ID пользователя в системе: {user_id}")

    try:
        # 1. Ищем пользователя в Jira по нику
        print("\n1. Поиск пользователя в Jira...")
        jira_user_info = jira_integration.find_user_by_display_name(jira_account)

        if not jira_user_info:
            print("Пользователь не найден в Jira")
            return False

        print(f"Найден пользователь в Jira:")
        print(f"  Account ID: {jira_user_info['account_id']}")
        print(f"  Display Name: {jira_user_info['display_name']}")
        print(f"  Email: {jira_user_info['email_address']}")
        print(f"  Active: {jira_user_info['active']}")

        # 2. Получаем проекты и задачи пользователя по accountId
        print("\n2. Получение проектов и задач пользователя...")
        account_id = jira_user_info['account_id']
        user_projects = jira_integration.get_user_projects_by_account_id(account_id)

        if not user_projects:
            print("У пользователя нет активных проектов в Jira")

            # Создаем проект по умолчанию для демонстрации
            default_project_data = {
                'key': 'DEFAULT',
                'name': 'Default Project',
                'tasks': []
            }
            user_projects = [default_project_data]

        # 3. Обрабатываем проекты
        print("\n3. Обработка проектов и задач...")
        for project_index, project_data in enumerate(user_projects, 1):
            print(f"\n  Проект {project_index}: {project_data['key']} - {project_data['name']}")
            print(f"  ID проекта: {project_data.get('id', 'N/A')}")

            # Получаем детальную информацию о проекте
            print(f"  Получение детальной информации о проекте...")
            project_details = jira_integration.get_project_details(project_data['key'])

            if project_details:
                print(f"  Описание: {project_details.get('description', 'Нет описания')[:100]}...")
                print(f"  Руководитель: {project_details.get('lead', 'Нет руководителя')}")
            else:
                print(f"  Детальная информация о проекте не получена")

            # Обрабатываем задачи
            tasks = project_data.get('tasks', [])
            print(f"  Задач в проекте: {len(tasks)}")

            for task_index, task_data in enumerate(tasks, 1):
                print(f"\n    Задача {task_index}:")
                print(f"      Ключ: {task_data['key']}")
                print(f"      Название: {task_data['summary'][:100]}...")

                # Обрабатываем спринт
                sprint_data = task_data.get('sprint')
                if sprint_data:
                    print(f"      Спринт: {sprint_data.get('name', 'Неизвестно')}")
                    print(f"      ID спринта: {sprint_data.get('id', 'N/A')}")

                    # Парсим даты спринта
                    if sprint_data.get('startDate'):
                        print(f"      Начало спринта: {sprint_data['startDate']}")
                    if sprint_data.get('endDate'):
                        print(f"      Конец спринта: {sprint_data['endDate']}")
                else:
                    print(f"      Спринт: нет")

        # 4. Получаем активные спринты для проектов
        print("\n4. Получение активных спринтов...")
        for project_data in user_projects:
            project_key = project_data.get('key')
            if project_key and project_key != 'DEFAULT':
                active_sprints = jira_integration.get_active_sprints(project_key)
                if active_sprints:
                    print(f"\n  Активные спринты в проекте {project_key}: {len(active_sprints)}")
                    for sprint in active_sprints:
                        print(f"    - {sprint.get('name')} (ID: {sprint.get('id')})")
                else:
                    print(f"\n  В проекте {project_key} нет активных спринтов")

        print("\n" + "=" * 60)
        print("СИНХРОНИЗАЦИЯ С JIRA ЗАВЕРШЕНА")
        print("=" * 60)

        # Возвращаем True для совместимости
        return True

    except Exception as e:
        print(f"\nОшибка при получении данных Jira: {e}")
        import traceback
        traceback.print_exc()
        return False


async def process_jira_registration(user_id: int, jira_account: str, user_name: str):
    """
    Асинхронная обработка регистрации Jira (только вывод в консоль)

    Args:
        user_id: ID пользователя
        jira_account: Ник пользователя в Jira
        user_name: Имя пользователя
    """
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def sync_jira_processing():
            return fetch_jira_user_data(user_id, jira_account, user_name)

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, sync_jira_processing)

        return result

    except Exception as e:
        print(f"Ошибка асинхронной обработки Jira: {e}")
        return False