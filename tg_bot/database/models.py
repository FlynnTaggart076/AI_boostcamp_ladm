import logging

from psycopg2.extras import RealDictCursor

from tg_bot.config.constants import VALID_ROLES
from tg_bot.database.connection import db_connection

logger = logging.getLogger(__name__)


class UserModel:
    """Модель пользователей - УПРОЩЕННАЯ версия"""

    # TODO: Добавить методы для Jira таблиц (проекты, задачи, спринты, доски)
    # при запуске бота, но они не используются в работе бота

    @staticmethod
    def get_user_by_telegram_username(telegram_username):
        """Получение пользователя по tg_username - ИСПОЛЬЗУЕТСЯ"""
        query = 'SELECT * FROM users WHERE tg_username = %s;'
        connection = db_connection.get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (telegram_username,))
            user = cursor.fetchone()
            return dict(user) if user else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_user_by_jira_name(jira_name):
        """Получение пользователя по jira_name - ИСПОЛЬЗУЕТСЯ при регистрации"""
        query = 'SELECT * FROM users WHERE jira_name = %s;'
        connection = db_connection.get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (jira_name,))
            user = cursor.fetchone()
            return dict(user) if user else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя по jira_name: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_user_by_jira_email(jira_email):
        """Получение пользователя по jira_email - ИСПОЛЬЗУЕТСЯ при регистрации"""
        query = 'SELECT * FROM users WHERE jira_email = %s;'
        connection = db_connection.get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (jira_email,))
            user = cursor.fetchone()
            return dict(user) if user else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя по jira_email: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def register_user(name, telegram_username, tg_id, role, jira_account=None):
        """Регистрация нового пользователя - ИСПОЛЬЗУЕТСЯ"""
        if role == 'ceo':
            role = 'CEO'

        if role not in VALID_ROLES:
            logger.error(f"Invalid role: {role}")
            return False

        # Определяем jira_name и jira_email из jira_account
        jira_name = None
        jira_email = None

        if jira_account:
            if '@' in jira_account:
                jira_email = jira_account
                # Пытаемся извлечь имя из email
                jira_name = jira_account.split('@')[0]
            else:
                jira_name = jira_account

        query = '''
        INSERT INTO users 
        (user_name, tg_username, tg_id, role, jira_name, jira_email)  -- ИЗМЕНИТЕ 'name' на 'user_name'
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (tg_username) 
        DO UPDATE SET
            user_name = EXCLUDED.user_name,  -- ИЗМЕНИТЕ 'name' на 'user_name'
            tg_id = EXCLUDED.tg_id,
            role = EXCLUDED.role,
            jira_name = EXCLUDED.jira_name,
            jira_email = EXCLUDED.jira_email
        RETURNING id_user;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute(query, (name, telegram_username, tg_id, role, jira_name, jira_email))
            connection.commit()
            logger.info(f"Пользователь зарегистрирован: {name} (jira: {jira_name})")
            return True
        except Exception as e:
            logger.error(f"Ошибка регистрации пользователя: {e}")
            connection.rollback()
            return False
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def update_existing_jira_user(user_id, telegram_username, tg_id, role, name):
        """Обновление существующего пользователя Jira при регистрации в Telegram"""
        query = '''
        UPDATE users 
        SET tg_username = %s, 
            tg_id = %s, 
            role = %s, 
            user_name = %s  -- ИЗМЕНИТЕ 'name' на 'user_name'
        WHERE id_user = %s
        RETURNING id_user;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute(query, (telegram_username, tg_id, role, name, user_id))
            user_id = cursor.fetchone()[0]
            connection.commit()
            logger.info(f"Пользователь Jira обновлен: ID {user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя Jira: {e}")
            connection.rollback()
            return False
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_users_by_role(role):
        """Получение пользователей по конкретной роли - ИСПОЛЬЗУЕТСЯ для отправки опросов"""
        query = '''
        SELECT * FROM users 
        WHERE role = %s 
        AND tg_id IS NOT NULL 
        AND tg_username IS NOT NULL;
        '''
        connection = db_connection.get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (role,))
            users = cursor.fetchall()
            return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"Ошибка получения пользователей по роли {role}: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_all_users_with_tg_id():
        """Получение всех пользователей с tg_id - ИСПОЛЬЗУЕТСЯ для опросов 'всем'"""
        query = '''
        SELECT * FROM users 
        WHERE tg_id IS NOT NULL 
        AND tg_username IS NOT NULL;
        '''
        connection = db_connection.get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            users = cursor.fetchall()
            return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def save_jira_user(jira_user_data):
        """Сохранение пользователя из Jira с поиском свободных ID"""
        jira_email = jira_user_data.get('jira_email')
        jira_name = jira_user_data.get('jira_name')

        if not jira_email and not jira_name:
            logger.warning("Jira user has no email or name, skipping")
            return None


        connection = db_connection.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor()

            # 1. Пытаемся найти существующего пользователя
            existing_user_id = None

            if jira_email:
                check_query = "SELECT id_user FROM users WHERE jira_email = %s"
                cursor.execute(check_query, (jira_email,))
                result = cursor.fetchone()
                if result:
                    existing_user_id = result[0]

            if not existing_user_id and jira_name:
                check_query = "SELECT id_user FROM users WHERE jira_name = %s AND jira_email IS NULL"
                cursor.execute(check_query, (jira_name,))
                result = cursor.fetchone()
                if result:
                    existing_user_id = result[0]

            if existing_user_id:
                # 2. Обновляем существующего пользователя
                update_fields = []
                update_values = []

                if jira_name:
                    update_fields.append("jira_name = %s")
                    update_values.append(jira_name)

                if jira_email:
                    update_fields.append("jira_email = %s")
                    update_values.append(jira_email)

                if update_fields:
                    update_values.append(existing_user_id)
                    update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id_user = %s"
                    cursor.execute(update_query, update_values)

                logger.debug(f"Jira user updated: {jira_name or jira_email}")
                user_id = existing_user_id
            else:
                # 3. Ищем свободный ID
                cursor.execute("""
                    WITH used_ids AS (
                        SELECT id_user FROM users 
                        WHERE id_user <= (SELECT COALESCE(MAX(id_user), 0) FROM users)
                    ),
                    all_ids AS (
                        SELECT generate_series(1, (SELECT COALESCE(MAX(id_user), 0) + 1 FROM users)) as id
                    ),
                    free_ids AS (
                        SELECT a.id 
                        FROM all_ids a 
                        LEFT JOIN used_ids u ON a.id = u.id_user 
                        WHERE u.id_user IS NULL 
                        ORDER BY a.id 
                        LIMIT 1
                    )
                    SELECT id FROM free_ids
                    UNION
                    SELECT (SELECT COALESCE(MAX(id_user), 0) + 1 FROM users)
                    ORDER BY id
                    LIMIT 1
                """)

                free_id_result = cursor.fetchone()
                next_id = free_id_result[0] if free_id_result else 1

                insert_query = """
                    INSERT INTO users (id_user, jira_name, jira_email, user_name)  -- ДОБАВЬТЕ user_name
                    VALUES (%s, %s, %s, %s)  -- ДОБАВЬТЕ 4-й параметр
                    ON CONFLICT (id_user) 
                    DO UPDATE SET
                        jira_name = EXCLUDED.jira_name,
                        jira_email = EXCLUDED.jira_email,
                        user_name = EXCLUDED.user_name  -- ДОБАВЬТЕ эту строку
                    RETURNING id_user;
                    """

                cursor.execute(insert_query, (
                    next_id,
                    jira_name if jira_name else None,
                    jira_email if jira_email else None,
                    jira_name if jira_name else None  # ДОБАВЬТЕ - используем jira_name как user_name
                ))
                user_id = cursor.fetchone()[0]
                logger.debug(f"Jira user created with ID {next_id}: {jira_name or jira_email}")

            connection.commit()
            return user_id

        except Exception as e:
            logger.error(f"Error saving Jira user: {e}")
            if connection:
                connection.rollback()
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()


class SurveyModel:
    """Модель опросов - ИСПОЛЬЗУЕТСЯ"""

    @staticmethod
    def create_survey(survey_data):
        """Создание нового опроса в БД - ИСПОЛЬЗУЕТСЯ"""
        query = '''
        INSERT INTO surveys 
        (datetime, question, role, state)
        VALUES (%s, %s, %s, %s)
        RETURNING id_survey;
        '''
        connection = db_connection.get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor()
            cursor.execute(query, (
                survey_data['datetime'],
                survey_data['question'],
                survey_data['role'],
                survey_data.get('state', 'active')
            ))
            survey_id = cursor.fetchone()[0]
            connection.commit()
            logger.info(f"Опрос создан с ID: {survey_id}")
            return survey_id
        except Exception as e:
            logger.error(f"Ошибка создания опроса: {e}")
            connection.rollback()
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_active_surveys():
        """Получение активных опросов - ИСПОЛЬЗУЕТСЯ"""
        query = '''
        SELECT * FROM surveys 
        WHERE state = 'active'
        ORDER BY datetime;
        '''
        connection = db_connection.get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            surveys = cursor.fetchall()
            return [dict(survey) for survey in surveys]
        except Exception as e:
            logger.error(f"Ошибка получения опросов: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_surveys_for_role_since(role, date_from):
        """Получение опросов для роли с ограничением по дате - НОВЫЙ МЕТОД"""
        if role is None:
            query = '''
                SELECT * FROM surveys 
                WHERE role IS NULL 
                  AND state = 'active'
                  AND datetime >= %s
                ORDER BY datetime DESC;
                '''
            params = (date_from,)
        else:
            query = '''
                SELECT * FROM surveys 
                WHERE role = %s 
                  AND state = 'active'
                  AND datetime >= %s
                ORDER BY datetime DESC;
                '''
            params = (role, date_from)

        connection = db_connection.get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, params)
            surveys = cursor.fetchall()
            return [dict(survey) for survey in surveys]
        except Exception as e:
            logger.error(f"Ошибка получения опросов по роли с датой: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_active_surveys_since(date_from):
        """Получение активных опросов с ограничением по дате - НОВЫЙ МЕТОД"""
        query = '''
            SELECT * FROM surveys 
            WHERE state = 'active'
              AND datetime >= %s
            ORDER BY datetime DESC;
            '''
        connection = db_connection.get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (date_from,))
            surveys = cursor.fetchall()
            return [dict(survey) for survey in surveys]
        except Exception as e:
            logger.error(f"Ошибка получения опросов с датой: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_surveys_for_role(role):
        """Получение опросов для определенной роли - ИСПОЛЬЗУЕТСЯ"""
        if role is None:
            query = '''
            SELECT * FROM surveys 
            WHERE role IS NULL AND state = 'active'
            ORDER BY datetime DESC;
            '''
            params = ()
        else:
            query = '''
            SELECT * FROM surveys 
            WHERE role = %s AND state = 'active'
            ORDER BY datetime DESC;
            '''
            params = (role,)
        connection = db_connection.get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, params)
            surveys = cursor.fetchall()
            return [dict(survey) for survey in surveys]
        except Exception as e:
            logger.error(f"Ошибка получения опросов по роли: {e}")
            return []
        finally:
            cursor.close()
            connection.close()


class ResponseModel:
    """Модель ответов на опросы - ИСПОЛЬЗУЕТСЯ"""

    @staticmethod
    def save_response(response_data):
        """Сохранение ответа на опрос - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        id_survey = response_data['id_survey']
        id_user = response_data['id_user']
        answer = response_data['answer']

        # Сначала проверяем существующий ответ
        existing_response = ResponseModel.get_user_response(id_survey, id_user)

        connection = db_connection.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor()

            if existing_response:
                # Обновляем существующий ответ
                query = '''
                    UPDATE responses 
                    SET answer = %s
                    WHERE id_user = %s AND id_survey = %s
                    RETURNING id_response;
                    '''
                params = (answer, id_user, id_survey)
            else:
                # Создаем новый ответ - БЕЗ УКАЗАНИЯ id_response
                query = '''
                    INSERT INTO responses 
                    (id_user, id_survey, answer)
                    VALUES (%s, %s, %s)
                    RETURNING id_response;
                    '''
                params = (id_user, id_survey, answer)

            cursor.execute(query, params)
            result = cursor.fetchone()
            response_id = result[0] if result else None
            connection.commit()

            if response_id:
                logger.info(f"Ответ сохранен: ID {response_id} для опроса #{id_survey}")
            else:
                logger.warning(f"Ответ не сохранен для опроса #{id_survey}")

            return response_id

        except Exception as e:
            logger.error(f"Ошибка сохранения ответа: {e}")
            connection.rollback()
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_user_response(id_survey, id_user):
        """Получение ответа пользователя на опрос"""
        query = '''
            SELECT * FROM responses 
            WHERE id_survey = %s AND id_user = %s;
            '''
        connection = db_connection.get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (id_survey, id_user))
            response = cursor.fetchone()
            return dict(response) if response else None
        except Exception as e:
            logger.error(f"Ошибка получения ответа: {e}")
            return None
        finally:
            cursor.close()
            connection.close()


class JiraDataModel:
    """Универсальная модель для загрузки данных Jira в БД при запуске"""

    @staticmethod
    def save_project(project_data):
        """Сохранение проекта в БД - используется только при загрузке"""
        # TODO: Реализовать сохранение проектов
        pass

    @staticmethod
    def save_board(board_data):
        """Сохранение доски в БД - используется только при загрузке"""
        # TODO: Реализовать сохранение досок
        pass

    @staticmethod
    def save_sprint(sprint_data):
        """Сохранение спринта в БД - используется только при загрузке"""
        # TODO: Реализовать сохранение спринтов
        pass

    @staticmethod
    def save_task(task_data):
        """Сохранение задачи в БД - используется только при загрузке"""
        # TODO: Реализовать сохранение задач
        pass


class BlockerModel:
    """Модель блокеров (проблем) - НЕ ИСПОЛЬЗУЕТСЯ в текущей версии"""

    @staticmethod
    def get_blockers_by_date(date):
        """TODO: Реализовать при необходимости"""
        return []


class DailyDigestModel:
    """Модель ежедневных дайджестов - НЕ ИСПОЛЬЗУЕТСЯ в текущей версии"""

    @staticmethod
    def get_daily_digest(date):
        """TODO: Реализовать при необходимости"""
        return []


class WeekDigestModel:
    """Модель еженедельных дайджестов - НЕ ИСПОЛЬЗУЕТСЯ в текущей версии"""

    @staticmethod
    def get_week_digest(start_date, end_date):
        """TODO: Реализовать при необходимости"""
        return []
