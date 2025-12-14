import os

import requests
from requests.auth import HTTPBasicAuth
import json
import time
from datetime import datetime, timedelta

# Конфигурационные данные
domain = os.getenv('JIRA_URL').replace('https://', '')
api_token = os.getenv('JIRA_API_TOKEN')
email = os.getenv('JIRA_EMAIL')


def get_all_tasks_by_search_api(jql_query=None, max_results=1000, output_file="all_tasks_by_search.json",
                                days_back=3650):
    """
    Получает все задачи через Search API (REST API 3)

    Args:
        jql_query (str): JQL запрос для фильтрации задач. Если None, будет использован запрос по умолчанию
        max_results (int): Максимальное количество задач
        output_file (str): Имя выходного JSON файла
        days_back (int): Сколько дней назад искать, если используется запрос по умолчанию
    """

    url = f"https://{domain}/rest/api/3/search/jql"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    # Автоматически генерируем JQL запрос, если он не указан
    if jql_query is None or jql_query.strip() == "":
        # Создаем запрос для задач за последние N дней
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Форматируем даты для JQL
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        jql_query = f"created >= '{start_str}' AND created <= '{end_str}' order by created DESC"
        print(f"Используется автоматический JQL запрос за последние {days_back} дней")
        print(f"JQL: {jql_query}")

    all_tasks = []
    start_at = 0
    max_per_page = 100  # Максимум на страницу

    # Базовые поля для запроса
    fields = [
        "summary", "status", "assignee", "reporter", "created", "updated",
        "priority", "issuetype", "project", "labels", "description"
    ]

    print(f"\nНачинаем сбор задач с JQL: {jql_query}")

    while True:
        params = {
            "jql": jql_query,
            "startAt": start_at,
            "maxResults": max_per_page,
            "fields": ",".join(fields)
        }

        print(f"  Страница {start_at // max_per_page + 1}: startAt={start_at}")

        try:
            response = requests.get(
                url,
                headers=headers,
                auth=auth,
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                issues = data.get('issues', [])
                total = data.get('total', 0)

                all_tasks.extend(issues)

                print(f"    Получено задач: {len(issues)}")

                # Проверяем, нужно ли продолжать пагинацию
                if start_at + len(issues) >= total:
                    print(f"    Достигнут конец списка. Всего задач: {total}")
                    break

                if len(all_tasks) >= max_results:
                    print(f"    Достигнут лимит в {max_results} задач")
                    break

                if not issues:
                    print("    Больше нет задач")
                    break

                start_at += max_per_page

                # Задержка для избежания rate limiting
                time.sleep(0.3)

            else:
                print(f"Ошибка при запросе: {response.status_code}")
                print(f"Ответ: {response.text[:500]}")
                break

        except Exception as e:
            print(f"Исключение при запросе: {str(e)}")
            break

    # Ограничиваем результат, если превышен max_results
    if len(all_tasks) > max_results:
        all_tasks = all_tasks[:max_results]

    # Сохраняем все задачи в JSON файл
    if all_tasks:
        # Подготовка данных для сохранения
        result_data = {
            "metadata": {
                "total_tasks": len(all_tasks),
                "jql_query": jql_query,
                "retrieved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "api_used": "rest/api/3/search/jql",
                "max_results_requested": max_results,
                "days_back": days_back if jql_query is None else "custom"
            },
            "tasks": all_tasks
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Всего собрано задач: {len(all_tasks)}")
        print(f"📁 Данные сохранены в файл: {output_file}")

        # Выводим статистику по проектам
        project_stats = {}
        status_stats = {}

        for task in all_tasks:
            project_key = task.get('fields', {}).get('project', {}).get('key', 'Unknown')
            project_stats[project_key] = project_stats.get(project_key, 0) + 1

            status_name = task.get('fields', {}).get('status', {}).get('name', 'Unknown')
            status_stats[status_name] = status_stats.get(status_name, 0) + 1

        print("\n📊 Распределение задач по проектам:")
        for project, count in sorted(project_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {project}: {count} задач")

        print("\n📊 Распределение задач по статусам:")
        for status, count in sorted(status_stats.items(), key=lambda x: x[1], reverse=True)[:10]:  # Топ-10 статусов
            print(f"  {status}: {count} задач")

        # Выводим примеры задач
        print("\n🔍 Примеры найденных задач:")
        for i, task in enumerate(all_tasks[:5]):
            key = task.get('key', 'N/A')
            summary = task.get('fields', {}).get('summary', 'N/A')
            project = task.get('fields', {}).get('project', {}).get('key', 'N/A')
            created = task.get('fields', {}).get('created', 'N/A')[:10]
            print(f"  {i + 1}. {key} ({project}): {summary[:60]}... (Создана: {created})")

        return all_tasks
    else:
        print("❌ Не найдено ни одной задачи")
        return []


def get_tasks_with_custom_jql(jql_query, max_results=500, output_file="custom_jql_tasks.json"):
    """
    Упрощенная функция для работы с кастомными JQL запросами

    Args:
        jql_query (str): JQL запрос (обязательный)
        max_results (int): Максимальное количество задач
        output_file (str): Имя выходного JSON файла
    """

    if not jql_query or jql_query.strip() == "":
        print("❌ Ошибка: JQL запрос не может быть пустым!")
        print("📝 Попробуйте один из вариантов:")
        print("   - 'project = SCRUM' - задачи из проекта SCRUM")
        print("   - 'created >= -30d' - задачи за последние 30 дней")
        print("   - 'status = \"To Do\"' - задачи в статусе To Do")
        print("   - 'assignee = currentUser()' - задачи, назначенные на вас")
        return []

    return get_all_tasks_by_search_api(
        jql_query=jql_query,
        max_results=max_results,
        output_file=output_file
    )


# Примеры использования функций
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ПРИМЕР : Получение всех задач через Search API (автоматический запрос)")
    print("=" * 70)

    all_tasks = get_all_tasks_by_search_api(
        jql_query=None,
        max_results=200,
        output_file="response/all_tasks_auto.json",
        days_back=365
    )
    #
    # print("\n" + "=" * 70)
    # print("ПРИМЕР 3: Получение задач с кастомным JQL запросом")
    # print("=" * 70)
    #
    #
    # # Более сложные запросы
    # complex_queries = [
    #     ("project in (SCRUM, AM7) AND status != Closed", "active_tasks_multiple_projects.json"),
    #     ("labels = bug AND priority = High", "high_priority_bugs.json"),
    #     # За последний год: 'created >= -365d'
    # ]
    #
    # for jql, filename in complex_queries:
    #     print(f"\n🔍 Выполняем сложный запрос: {jql}")
    #     get_tasks_with_custom_jql(jql, 150, filename)
