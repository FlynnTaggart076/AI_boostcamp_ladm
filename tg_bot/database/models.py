from tg_bot.config.roles_config import ALL_ROLES, ROLE_CATEGORIES
from tg_bot.config.constants import VALID_ROLES, SURVEY_STATUS
from tg_bot.database.connection import db_connection
from psycopg2.extras import RealDictCursor
import logging

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
    def get_user_by_tg_id(tg_id):
        """Получение пользователя по tg_id - ИСПОЛЬЗУЕТСЯ"""
        query = 'SELECT * FROM users WHERE tg_id = %s;'
        connection = db_connection.get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (tg_id,))
            user = cursor.fetchone()
            return dict(user) if user else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя по tg_id: {e}")
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
        (name, tg_username, tg_id, role, jira_name, jira_email)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (tg_username) 
        DO UPDATE SET
            name = EXCLUDED.name,
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
            user_id = cursor.fetchone()[0]
            connection.commit()
            logger.info(f"✅ Пользователь зарегистрирован: {name} (jira: {jira_name})")
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
        """Обновление существующего пользователя Jira при регистрации в Telegram - ИСПОЛЬЗУЕТСЯ"""
        query = '''
        UPDATE users 
        SET tg_username = %s, tg_id = %s, role = %s, name = %s
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
            logger.info(f"✅ Пользователь Jira обновлен: ID {user_id}")
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
    def get_users_by_role_category(role_category):
        """Получение пользователей по категории ролей - ИСПОЛЬЗУЕТСЯ для отправки опросов"""
        if role_category not in ROLE_CATEGORIES:
            return []
        role_types = list(ROLE_CATEGORIES[role_category]['subtypes'].keys())
        if not role_types:
            return []
        placeholders = ', '.join(['%s'] * len(role_types))
        query = f'''
        SELECT * FROM users 
        WHERE role IN ({placeholders}) 
        AND tg_id IS NOT NULL 
        AND tg_username IS NOT NULL;
        '''
        connection = db_connection.get_connection()
        if not connection:
            return []
        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, tuple(role_types))
            users = cursor.fetchall()
            return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"Ошибка получения пользователей по категории {role_category}: {e}")
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
    def get_all_jira_users():
        """Получение всех пользователей из Jira (даже без Telegram) - ИСПОЛЬЗУЕТСЯ при загрузке"""
        query = '''
        SELECT * FROM users 
        WHERE jira_name IS NOT NULL OR jira_email IS NOT NULL;
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
            logger.error(f"Ошибка получения всех пользователей Jira: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def save_jira_user(jira_user_data):
        """Сохранение пользователя из Jira при загрузке данных - ИСПОЛЬЗУЕТСЯ при запуске"""
        query = '''
        INSERT INTO users 
        (jira_name, jira_email)
        VALUES (%s, %s)
        ON CONFLICT (jira_email) 
        DO UPDATE SET
            jira_name = EXCLUDED.jira_name
        RETURNING id_user;
        '''
        connection = db_connection.get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor()
            cursor.execute(query, (
                jira_user_data.get('jira_name'),
                jira_user_data.get('jira_email')
            ))
            user_id = cursor.fetchone()[0]
            connection.commit()
            logger.debug(f"Пользователь Jira сохранен: {jira_user_data.get('jira_name')}")
            return user_id
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя Jira: {e}")
            connection.rollback()
            return None
        finally:
            cursor.close()
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
            logger.info(f"✅ Опрос создан с ID: {survey_id}")
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
        """Сохранение ответа на опрос - ИСПОЛЬЗУЕТСЯ"""
        query = '''
        INSERT INTO responses 
        (id_user, id_survey, answer)
        VALUES (%s, %s, %s)
        ON CONFLICT (id_user, id_survey) 
        DO UPDATE SET
            answer = EXCLUDED.answer
        RETURNING id_response;
        '''
        connection = db_connection.get_connection()
        if not connection:
            return None
        try:
            cursor = connection.cursor()
            cursor.execute(query, (
                response_data['id_user'],
                response_data['id_survey'],
                response_data['answer']
            ))
            response_id = cursor.fetchone()[0]
            connection.commit()
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
        """Получение ответа пользователя на опрос - ИСПОЛЬЗУЕТСЯ"""
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

