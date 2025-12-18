"""
Обработчик Jira данных при регистрации пользователя - УПРОЩЕННАЯ версия
"""
import logging
from tg_bot.services.jira_integration import jira_integration

logger = logging.getLogger(__name__)


def fetch_jira_user_data(user_id: int, jira_account: str, user_name: str):
    """
    Получение данных Jira для пользователя (только вывод для отладки)
    Теперь основная загрузка происходит через jira_loader.py
    """
    print("=" * 60)
    print("ПРОВЕРКА JIRA АККАУНТА ПРИ РЕГИСТРАЦИИ")
    print("=" * 60)
    print(f"Пользователь: {user_name}")
    print(f"Jira аккаунт: {jira_account}")

    try:
        # Ищем пользователя в Jira
        print("\n1. Поиск пользователя в Jira...")
        jira_user_info = jira_integration.find_user_by_display_name(jira_account)

        if not jira_user_info:
            print("Пользователь не найден в Jira")
            print("Это нормально, если пользователь ввел неверный аккаунт")
            print("или если данные Jira еще не загружены в систему")
            return True  # Все равно возвращаем True, регистрация продолжается

        print(f"Пользователь найден в Jira:")
        print(f"   Account ID: {jira_user_info['account_id']}")
        print(f"   Display Name: {jira_user_info['display_name']}")
        print(f"   Email: {jira_user_info['email_address']}")

        return True

    except Exception as e:
        print(f"\nОшибка при проверке Jira: {e}")
        print("Регистрация продолжается без данных Jira")
        return True  # Все равно продолжаем регистрацию


async def process_jira_registration(user_id: int, jira_account: str, user_name: str):
    """
    Асинхронная обработка регистрации Jira
    Теперь только проверка, основная загрузка в jira_loader.py
    """
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def sync_jira_check():
            return fetch_jira_user_data(user_id, jira_account, user_name)

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, sync_jira_check)

        return result

    except Exception as e:
        print(f"Ошибка асинхронной обработки Jira: {e}")
        return True
