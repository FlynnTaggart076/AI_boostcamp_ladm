# unified_jira_diagnostics.py
import requests
from config.settings import config


def test_jira_connection_detailed():
    """Детальная проверка подключения к Jira API"""
    url = f"{config.JIRA_URL}/rest/api/3/myself"

    print("=" * 50)
    print("ДЕТАЛЬНАЯ ДИАГНОСТИКА JIRA API")
    print("=" * 50)

    # Выводим конфигурацию (без пароля)
    print(f"JIRA_URL: {config.JIRA_URL}")
    print(f"JIRA_EMAIL: {config.JIRA_EMAIL}")
    print(f"JIRA_API_TOKEN длина: {len(config.JIRA_API_TOKEN) if config.JIRA_API_TOKEN else 0} символов")
    print(f"JIRA_PROJECT_KEY: {config.JIRA_PROJECT_KEY}")

    # Проверяем, что все поля заполнены
    if not all([config.JIRA_URL, config.JIRA_EMAIL, config.JIRA_API_TOKEN]):
        print("\n❌ Ошибка: Не все Jira переменные заполнены!")
        return None

    # Формируем заголовки
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Показываем, что отправляем (первые 10 символов токена)
    token_preview = config.JIRA_API_TOKEN[:10] + "..." if config.JIRA_API_TOKEN else "Нет токена"
    print(f"\nОтправляю запрос к: {url}")
    print(f"Аутентификация: {config.JIRA_EMAIL}:{token_preview}")

    try:
        # Делаем запрос с таймаутом
        response = requests.get(
            url,
            auth=(config.JIRA_EMAIL, config.JIRA_API_TOKEN),
            headers=headers,
            timeout=10
        )

        print(f"\nСтатус код: {response.status_code}")

        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Успешно! Вы вошли как: {user_data.get('displayName')}")
            print(f"   Account ID: {user_data.get('accountId')}")
            print(f"   Email: {user_data.get('emailAddress')}")
            return user_data

        elif response.status_code == 401:
            print("❌ Ошибка 401: Не авторизовано")
            print("Возможные причины:")
            print("1. Неверный email (используйте email от Atlassian аккаунта)")
            print("2. Неверный или истекший API токен")
            print("3. Токен не имеет нужных разрешений")
            print(f"\nПолный ответ: {response.text[:500]}")

            # Попробуем альтернативный метод аутентификации
            print("\n" + "=" * 50)
            print("Пробую альтернативные методы...")

            # Метод 1: Проверка базового URL
            test_url = f"{config.JIRA_URL}/rest/api/3/serverInfo"
            print(f"\nТест 1: Проверка сервера: {test_url}")
            try:
                resp = requests.get(test_url, timeout=5)
                print(f"   Статус: {resp.status_code}")
                if resp.status_code == 200:
                    print("   ✅ Сервер доступен")
                else:
                    print(f"   ❌ Сервер недоступен: {resp.text[:200]}")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")

            return None

        else:
            print(f"❌ Неожиданная ошибка: {response.status_code}")
            print(f"Ответ: {response.text[:500]}")
            return None

    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения: Не удается соединиться с сервером")
        print(f"Проверьте URL: {config.JIRA_URL}")
        return None

    except Exception as e:
        print(f"❌ Неизвестная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_jira_projects_and_issues(user_data=None):
    """Тестирование доступных проектов и запросов задач"""
    if not user_data:
        print("\n" + "=" * 50)
        print("Сначала необходимо пройти аутентификацию")
        print("=" * 50)
        return

    base_url = config.JIRA_URL
    auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # 1. Проверка доступных проектов
    print("\n" + "=" * 50)
    print("ПРОВЕРКА ДОСТУПНЫХ ПРОЕКТОВ")
    print("=" * 50)

    response = requests.get(
        f"{base_url}/rest/api/3/project/search",
        headers=headers,
        auth=auth,
        timeout=10
    )

    if response.status_code == 200:
        projects = response.json().get('values', [])
        print(f"✅ Найдено проектов: {len(projects)}")
        for project in projects[:5]:  # Показываем первые 5
            print(f"   • {project['key']}: {project['name']}")

        if len(projects) > 5:
            print(f"   ... и еще {len(projects) - 5} проектов")
    else:
        print(f"❌ Ошибка при получении проектов: {response.status_code}")
        print(f"Ответ: {response.text[:200]}")
        return

    # 2. Тестовый запрос задач с простым JQL
    print("\n" + "=" * 50)
    print("ТЕСТОВЫЕ ЗАПРОСЫ ЗАДАЧ")
    print("=" * 50)

    account_id = user_data.get('accountId')

    # Попробуйте разные варианты JQL:
    jql_queries = [
        f'assignee = "{account_id}"',
        f'assignee in ("{account_id}")',
        f'assignee = currentUser()',
        f'project = {config.JIRA_PROJECT_KEY}' if config.JIRA_PROJECT_KEY else 'project = TES',
        'status != Done',
        'created >= -30d'  # Задачи созданные за последние 30 дней
    ]

    for i, jql in enumerate(jql_queries, 1):
        print(f"\n   Попытка {i}: JQL = {jql}")

        payload = {
            'jql': jql,
            'maxResults': 5,
            'fields': ['key', 'summary', 'project', 'status']
        }

        try:
            response = requests.post(
                f"{base_url}/rest/api/3/search/jql",
                headers=headers,
                auth=auth,
                json=payload,
                timeout=10
            )

            print(f"   Статус: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                issues = data.get('issues', [])
                print(f"   Найдено задач: {total}")

                if issues:
                    for issue in issues[:3]:  # Показываем первые 3 задачи
                        key = issue.get('key', 'N/A')
                        summary = issue.get('fields', {}).get('summary', 'N/A')
                        status = issue.get('fields', {}).get('status', {}).get('name', 'N/A')
                        print(f"      • {key}: {summary} [{status}]")
            else:
                print(f"   Ошибка: {response.text[:200]}")

        except Exception as e:
            print(f"   ❌ Исключение при запросе: {e}")


def full_jira_diagnostic():
    """Полная диагностика подключения к Jira"""
    print("\n" + "=" * 60)
    print("ПОЛНАЯ ДИАГНОСТИКА JIRA ПОДКЛЮЧЕНИЯ")
    print("=" * 60)

    # Шаг 1: Детальная проверка подключения
    user_data = test_jira_connection_detailed()

    # Шаг 2: Если подключение успешно, проверяем проекты и задачи
    if user_data:
        test_jira_projects_and_issues(user_data)

    print("\n" + "=" * 60)
    print("ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("=" * 60)


if __name__ == "__main__":
    full_jira_diagnostic()
