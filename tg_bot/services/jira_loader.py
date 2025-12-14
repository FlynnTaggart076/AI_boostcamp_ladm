# -*- coding: utf-8 -*-
import asyncio
import logging
import requests

from tg_bot.database.connection import db_connection
from tg_bot.database.models import UserModel
from tg_bot.config.settings import config

logger = logging.getLogger(__name__)


class JiraLoader:
    def __init__(self):
        self.base_url = config.JIRA_URL
        # Логируем информацию о токене
        if config.JIRA_API_TOKEN:
            logger.info(f"Jira токен получен, длина: {len(config.JIRA_API_TOKEN)}")
            logger.info(f"Первые 10 символов токена: {config.JIRA_API_TOKEN[:10]}...")
            logger.info(f"Последние 10 символов токена: ...{config.JIRA_API_TOKEN[-10:]}")

        self.auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        # Тестовый запрос для проверки подключения
        self.test_connection()

    def test_connection(self):
        """Тестовый запрос для проверки подключения к Jira"""
        if not self.base_url or not config.JIRA_EMAIL or not config.JIRA_API_TOKEN:
            logger.warning("Jira настройки неполные, пропускаем тест подключения")
            return

        try:
            test_url = f"{self.base_url}/rest/api/3/myself"
            logger.info(f"Проверка подключения к Jira: {test_url}")

            response = requests.get(
                test_url,
                headers=self.headers,
                auth=self.auth,
                timeout=10
            )

            if response.status_code == 200:
                logger.info("Подключение к Jira успешно!")
            else:
                logger.error(f"Ошибка подключения к Jira: {response.status_code}")
                logger.error(f"Ответ: {response.text[:200]}")

        except Exception as e:
            logger.error(f"Ошибка при тесте подключения к Jira: {e}")

    def load_all_data(self) -> bool:
        try:
            logger.info("Начало загрузки данных из Jira...")

            # 1. Загружаем пользователей
            if not self.load_users():
                logger.error("Ошибка загрузки пользователей")
                return False

            # 2. Загружаем проекты
            if not self.load_projects():
                logger.error("Ошибка загрузки проектов")
                return False

            # 3. Загружаем доски
            if not self.load_boards():
                logger.error("Ошибка загрузки досок")
                return False

            # 4. Загружаем спринты
            if not self.load_sprints():
                logger.error("Ошибка загрузки спринтов")
                return False

            # 5. Загружаем задачи
            if not self.load_tasks():
                logger.error("Ошибка загрузки задач")
                return False

            logger.info("Все данные Jira успешно загружены в БД")
            return True

        except Exception as e:
            logger.error(f"Ошибка при загрузке данных Jira: {e}")
            return False

    def load_users(self) -> bool:
        """Загрузка всех пользователей из Jira в таблицу users"""
        try:
            logger.info("Загрузка пользователей из Jira...")

            url = f"{self.base_url}/rest/api/3/users/search"
            all_users = []
            start_at = 0
            max_results = 100

            while True:
                params = {
                    'startAt': start_at,
                    'maxResults': max_results
                }

                response = requests.get(
                    url,
                    headers=self.headers,
                    auth=self.auth,
                    params=params,
                    timeout=30
                )

                if response.status_code == 200:
                    users_batch = response.json()
                    if not users_batch:
                        break

                    all_users.extend(users_batch)
                    logger.info(f"Загружено пользователей: {len(users_batch)} (всего: {len(all_users)})")

                    if len(users_batch) < max_results:
                        break

                    start_at += max_results
                else:
                    logger.error(f"Ошибка получения пользователей: {response.status_code}")
                    return False

            # Сохраняем пользователей в БД
            saved_count = 0
            for user in all_users:
                if user.get('active', False):  # Только активных пользователей
                    user_data = {
                        'jira_name': user.get('displayName'),
                        'jira_email': user.get('emailAddress')
                    }

                    # Сохраняем через UserModel
                    user_id = UserModel.save_jira_user(user_data)
                    if user_id:
                        saved_count += 1

            logger.info(f"Пользователей сохранено в БД: {saved_count}/{len(all_users)}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            return False

    def load_projects(self) -> bool:
        """Загрузка всех проектов из Jira"""
        try:
            logger.info("Загрузка проектов из Jira...")

            url = f"{self.base_url}/rest/api/3/project/search"

            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                projects = data.get('values', [])

                # Сохраняем проекты в БД
                saved_count = 0
                for project in projects:
                    project_key = project.get('key', '')
                    project_name = project.get('name', '')

                    if project_key:  # Проверяем, что ключ проекта существует
                        query = '''
                        INSERT INTO projects 
                        (project_key, name, projecttypekey, jira_name, jira_email)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (project_key) 
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            projecttypekey = EXCLUDED.projecttypekey,
                            jira_name = EXCLUDED.jira_name,
                            jira_email = EXCLUDED.jira_email;
                        '''

                        connection = db_connection.get_connection()
                        if connection:
                            try:
                                cursor = connection.cursor()
                                cursor.execute(query, (
                                    project_key,
                                    project_name,
                                    project.get('projectTypeKey'),
                                    project.get('lead', {}).get('displayName'),
                                    project.get('lead', {}).get('emailAddress')
                                ))
                                connection.commit()
                                saved_count += 1
                            except Exception as e:
                                logger.error(f"Ошибка сохранения проекта {project_key}: {e}")
                                connection.rollback()
                            finally:
                                cursor.close()
                                connection.close()

                logger.info(f"Проектов сохранено в БД: {saved_count}/{len(projects)}")
                return True
            else:
                logger.error(f"Ошибка получения проектов: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Ошибка загрузки проектов: {e}")
            return False

    def load_boards(self) -> bool:
        """Загрузка всех досок из Jira"""
        try:
            logger.info("Загрузка досок из Jira...")

            url = f"{self.base_url}/rest/agile/1.0/board"
            all_boards = []
            start_at = 0
            max_results = 100

            while True:
                params = {
                    'startAt': start_at,
                    'maxResults': max_results
                }

                response = requests.get(
                    url,
                    headers=self.headers,
                    auth=self.auth,
                    params=params,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    boards_batch = data.get('values', [])
                    if not boards_batch:
                        break

                    all_boards.extend(boards_batch)
                    logger.info(f"Загружено досок: {len(boards_batch)} (всего: {len(all_boards)})")

                    if len(boards_batch) < max_results:
                        break

                    start_at += max_results
                else:
                    logger.error(f"Ошибка получения досок: {response.status_code}")
                    return False

            # Сохраняем доски в БД
            saved_count = 0
            for board in all_boards:
                board_id = board.get('id')
                board_name = board.get('name', '')
                project_key = board.get('location', {}).get('projectKey', '')

                if board_id and board_name:
                    query = '''
                    INSERT INTO boards 
                    (id_board, name, project_key)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_board) 
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        project_key = EXCLUDED.project_key;
                    '''

                    connection = db_connection.get_connection()
                    if connection:
                        try:
                            cursor = connection.cursor()
                            cursor.execute(query, (board_id, board_name, project_key))
                            connection.commit()
                            saved_count += 1
                        except Exception as e:
                            logger.error(f"Ошибка сохранения доски {board_id}: {e}")
                            connection.rollback()
                        finally:
                            cursor.close()
                            connection.close()

            logger.info(f"Досок сохранено в БД: {saved_count}/{len(all_boards)}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки досок: {e}")
            return False

    def load_sprints(self) -> bool:
        """Загрузка всех спринтов из Jira"""
        try:
            logger.info("Загрузка спринтов из Jira...")

            # Сначала получаем все доски из БД
            connection = db_connection.get_connection()
            if not connection:
                logger.error("Нет подключения к БД для получения досок")
                return False

            try:
                cursor = connection.cursor()
                cursor.execute("SELECT id_board FROM boards")
                board_ids = [row[0] for row in cursor.fetchall()]
            except Exception as e:
                logger.error(f"Ошибка получения досок из БД: {e}")
                return False
            finally:
                cursor.close()
                connection.close()

            if not board_ids:
                logger.warning("В БД нет досок, пропускаем загрузку спринтов")
                return True

            # Загружаем спринты для каждой доски
            total_saved = 0
            for board_id in board_ids:
                try:
                    url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint"

                    response = requests.get(
                        url,
                        headers=self.headers,
                        auth=self.auth,
                        timeout=30
                    )

                    if response.status_code == 200:
                        data = response.json()
                        sprints = data.get('values', [])

                        # Сохраняем спринты в БД
                        for sprint in sprints:
                            sprint_id = sprint.get('id')
                            sprint_name = sprint.get('name', '')

                            if sprint_id and sprint_name:
                                query = '''
                                INSERT INTO sprints 
                                (id_sprint, state, start_date, name, id_board, jira_name, jira_email)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id_sprint) 
                                DO UPDATE SET
                                    state = EXCLUDED.state,
                                    start_date = EXCLUDED.start_date,
                                    name = EXCLUDED.name,
                                    id_board = EXCLUDED.id_board,
                                    jira_name = EXCLUDED.jira_name,
                                    jira_email = EXCLUDED.jira_email;
                                '''

                                connection = db_connection.get_connection()
                                if connection:
                                    try:
                                        cursor = connection.cursor()
                                        cursor.execute(query, (
                                            sprint_id,
                                            sprint.get('state'),
                                            sprint.get('startDate'),
                                            sprint_name,
                                            board_id,
                                            sprint.get('lead', {}).get('displayName'),
                                            sprint.get('lead', {}).get('emailAddress')
                                        ))
                                        connection.commit()
                                        total_saved += 1
                                    except Exception as e:
                                        logger.error(f"Ошибка сохранения спринта {sprint_id}: {e}")
                                        connection.rollback()
                                    finally:
                                        cursor.close()
                                        connection.close()

                        logger.info(f"Доска {board_id}: найдено {len(sprints)} спринтов")
                    else:
                        logger.warning(f"Доска {board_id}: нет спринтов или ошибка {response.status_code}")

                except Exception as e:
                    logger.error(f"Ошибка загрузки спринтов для доски {board_id}: {e}")
                    continue

            logger.info(f"Спринтов сохранено в БД: {total_saved}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки спринтов: {e}")
            return False

    def load_tasks(self, days_back: int = 365) -> bool:
        """Загрузка задач из Jira (за последние N дней)"""
        try:
            logger.info("Загрузка задач из Jira...")

            # JQL запрос для задач за последние N дней
            jql = f'created >= -{days_back}d order by created DESC'

            url = f"{self.base_url}/rest/api/3/search/jql"

            all_tasks = []
            start_at = 0
            max_results = 100
            max_total = 1000  # Максимум задач для загрузки

            while len(all_tasks) < max_total:
                payload = {
                    'jql': jql,
                    'startAt': start_at,
                    'maxResults': max_results,
                    'fields': ['key', 'summary', 'project', 'status', 'assignee',
                               'reporter', 'priority', 'issuetype', 'sprint', 'created']
                }

                response = requests.post(
                    url,
                    headers=self.headers,
                    auth=self.auth,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    tasks_batch = data.get('issues', [])
                    total = data.get('total', 0)

                    if not tasks_batch:
                        break

                    all_tasks.extend(tasks_batch)
                    logger.info(f"Загружено задач: {len(tasks_batch)} (всего: {len(all_tasks)} из {total})")

                    if start_at + len(tasks_batch) >= total or len(all_tasks) >= max_total:
                        break

                    start_at += max_results
                else:
                    logger.error(f"Ошибка получения задач: {response.status_code}")
                    return False

            # Сохраняем задачи в БД
            saved_count = 0
            for task in all_tasks:
                try:
                    task_id = task.get('id')
                    task_key = task.get('key', '')

                    if not task_id or not task_key:
                        continue

                    fields = task.get('fields', {})

                    # Определяем ID спринта
                    id_sprint = None
                    sprint_data = fields.get('sprint')
                    if sprint_data:
                        if isinstance(sprint_data, list) and sprint_data:
                            id_sprint = sprint_data[0].get('id')
                        elif isinstance(sprint_data, dict):
                            id_sprint = sprint_data.get('id')

                    # Определяем ID пользователя (assignee)
                    id_user = None
                    assignee = fields.get('assignee')
                    if assignee and assignee.get('emailAddress'):
                        # Пытаемся найти пользователя в БД по email
                        user = UserModel.get_user_by_jira_email(assignee['emailAddress'])
                        if user:
                            id_user = user.get('id_user')

                    query = '''
                    INSERT INTO tasks 
                    (id_task, task_key, summary, priority_name, project_key, reporter_name, 
                     assignee_name, issue_type, hierarchylevel, status_key, id_sprint, id_user)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id_task) 
                    DO UPDATE SET
                        task_key = EXCLUDED.task_key,
                        summary = EXCLUDED.summary,
                        priority_name = EXCLUDED.priority_name,
                        project_key = EXCLUDED.project_key,
                        reporter_name = EXCLUDED.reporter_name,
                        assignee_name = EXCLUDED.assignee_name,
                        issue_type = EXCLUDED.issue_type,
                        hierarchylevel = EXCLUDED.hierarchylevel,
                        status_key = EXCLUDED.status_key,
                        id_sprint = EXCLUDED.id_sprint,
                        id_user = EXCLUDED.id_user;
                    '''

                    connection = db_connection.get_connection()
                    if connection:
                        try:
                            cursor = connection.cursor()
                            cursor.execute(query, (
                                task_id,
                                task_key,
                                fields.get('summary', ''),
                                fields.get('priority', {}).get('name'),
                                fields.get('project', {}).get('key', ''),
                                fields.get('reporter', {}).get('displayName'),
                                fields.get('assignee', {}).get('displayName'),
                                fields.get('issuetype', {}).get('name'),
                                0,  # hierarchylevel - по умолчанию 0
                                fields.get('status', {}).get('name'),
                                id_sprint,
                                id_user
                            ))
                            connection.commit()
                            saved_count += 1
                        except Exception as e:
                            logger.error(f"Ошибка сохранения задачи {task_key}: {e}")
                            connection.rollback()
                        finally:
                            cursor.close()
                            connection.close()

                except Exception as e:
                    logger.error(f"Ошибка обработки задачи: {e}")
                    continue

            logger.info(f"Задач сохранено в БД: {saved_count}/{len(all_tasks)}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки задач: {e}")
            return False

    def clear_old_data(self) -> bool:
        """Очистка старых данных перед загрузкой (опционально)"""
        try:
            logger.info("Очистка старых данных Jira...")

            connection = db_connection.get_connection()
            if not connection:
                return False

            tables_to_clear = ['tasks', 'sprints', 'boards', 'projects']
            cleared_count = 0

            try:
                cursor = connection.cursor()

                for table in tables_to_clear:
                    cursor.execute(f"DELETE FROM {table}")
                    cleared_count += 1
                    logger.info(f"Таблица {table} очищена")

                connection.commit()
                logger.info(f"Очищено таблиц: {cleared_count}")
                return True

            except Exception as e:
                logger.error(f"Ошибка очистки данных: {e}")
                connection.rollback()
                return False
            finally:
                cursor.close()
                connection.close()

        except Exception as e:
            logger.error(f"Ошибка при очистке данных: {e}")
            return False


# Создаем глобальный экземпляр загрузчика
jira_loader = JiraLoader()


def sync_jira_data_with_progress(update=None, context=None):
    """Ручная синхронизация данных Jira с отправкой прогресса в Telegram"""
    try:
        if update and context:
            # Отправляем начальное сообщение
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("Начинаю синхронизацию..."),
                asyncio.get_event_loop()
            )

        logger.info("Ручная синхронизация данных Jira...")

        # 1. Очистка старых данных
        if update and context:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("Очистка старых данных..."),
                asyncio.get_event_loop()
            )

        jira_loader.clear_old_data()

        # 2. Загрузка пользователей
        if update and context:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("Загрузка пользователей..."),
                asyncio.get_event_loop()
            )

        if not jira_loader.load_users():
            logger.error("Ошибка загрузки пользователей")
            if update and context:
                asyncio.run_coroutine_threadsafe(
                    update.message.reply_text("Ошибка загрузки пользователей"),
                    asyncio.get_event_loop()
                )
            return False

        # 3. Загрузка проектов
        if update and context:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("Загрузка проектов..."),
                asyncio.get_event_loop()
            )

        if not jira_loader.load_projects():
            logger.error("Ошибка загрузки проектов")
            if update and context:
                asyncio.run_coroutine_threadsafe(
                    update.message.reply_text("Ошибка загрузки проектов, продолжаем..."),
                    asyncio.get_event_loop()
                )

        # 4. Загрузка досок
        if update and context:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("Загрузка досок..."),
                asyncio.get_event_loop()
            )

        if not jira_loader.load_boards():
            logger.error("Ошибка загрузки досок")
            if update and context:
                asyncio.run_coroutine_threadsafe(
                    update.message.reply_text("Ошибка загрузки досок, продолжаем..."),
                    asyncio.get_event_loop()
                )

        # 5. Загрузка спринтов
        if update and context:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("Загрузка спринтов..."),
                asyncio.get_event_loop()
            )

        if not jira_loader.load_sprints():
            logger.error("Ошибка загрузки спринтов")
            if update and context:
                asyncio.run_coroutine_threadsafe(
                    update.message.reply_text("Ошибка загрузки спринтов, продолжаем..."),
                    asyncio.get_event_loop()
                )

        # 6. Загрузка задач
        if update and context:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("Загрузка задач..."),
                asyncio.get_event_loop()
            )

        if not jira_loader.load_tasks():
            logger.error("Ошибка загрузки задач")
            if update and context:
                asyncio.run_coroutine_threadsafe(
                    update.message.reply_text("Ошибка загрузки задач, продолжаем..."),
                    asyncio.get_event_loop()
                )

        logger.info("Ручная синхронизация завершена успешно")

        if update and context:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text(
                    "Синхронизация с Jira завершена успешно!\n"
                    "Все данные обновлены:\n"
                    "• Пользователи\n"
                    "• Проекты\n"
                    "• Доски\n"
                    "• Спринты\n"
                    "• Задачи"
                ),
                asyncio.get_event_loop()
            )

        return True

    except Exception as e:
        logger.error(f"Ошибка при ручной синхронизации: {e}")

        if update and context:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text(
                    f"Произошла ошибка при синхронизации:\n"
                    f"{str(e)[:200]}..."
                ),
                asyncio.get_event_loop()
            )

        return False


# Функции для удобного использования
def load_jira_data_on_startup(clear_old: bool = False) -> bool:
    """Загрузка данных Jira при запуске бота"""
    try:
        logger.info("Запуск загрузки данных Jira при старте бота")

        if clear_old:
            if not jira_loader.clear_old_data():
                logger.warning("Не удалось очистить старые данные, продолжаем загрузку")

        success = jira_loader.load_all_data()

        if success:
            logger.info("Данные Jira успешно загружены при старте бота")
        else:
            logger.error("Не удалось загрузить данные Jira при старте бота")

        return success

    except Exception as e:
        logger.error(f"Критическая ошибка при загрузке данных Jira: {e}")
        return False


def sync_jira_data_manually() -> bool:
    """Ручная синхронизация данных Jira (для команды /syncjira)"""
    try:
        logger.info("Ручная синхронизация данных Jira...")

        # Очищаем старые данные перед загрузкой новых
        jira_loader.clear_old_data()

        success = jira_loader.load_all_data()

        if success:
            logger.info("Ручная синхронизация завершена успешно")
        else:
            logger.error("Ручная синхронизация завершена с ошибками")

        return success

    except Exception as e:
        logger.error(f"Ошибка при ручной синхронизации: {e}")
        return False