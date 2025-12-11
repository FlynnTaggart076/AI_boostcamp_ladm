from config.roles_config import ALL_ROLES
from config.constants import VALID_ROLES, SURVEY_STATUS
from database.connection import db_connection  # Абсолютный импорт внутри пакета
from psycopg2.extras import RealDictCursor
import logging


logger = logging.getLogger(__name__)


class UserModel:

    @staticmethod
    def get_user_by_telegram_username(telegram_username):
        """Получение пользователя по tg_username"""
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
        """Получение пользователя по tg_id"""
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
    def get_user_by_name(name):
        """Получение пользователя по имени (name)"""
        query = 'SELECT * FROM users WHERE name ILIKE %s;'

        connection = db_connection.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (name.strip(),))
            user = cursor.fetchone()
            return dict(user) if user else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя по имени: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def register_user(name, telegram_username, tg_id, role, jira_account=None):
        """Регистрация нового пользователя с tg_id"""
        # Приводим роль к правильному формату перед проверкой
        if role == 'ceo':  # Если пользователь ввел строчными
            role = 'CEO'  # Преобразуем в заглавные

        # Проверяем, что роль валидная
        if role not in VALID_ROLES:
            logger.error(f"Invalid role: {role}")
            logger.error(f"Available roles: {list(ALL_ROLES.keys())}")
            return False

        query = '''
        INSERT INTO users 
        (name, tg_username, tg_id, jira_account, role)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (tg_username) 
        DO UPDATE SET
            name = EXCLUDED.name,
            tg_id = EXCLUDED.tg_id,
            role = EXCLUDED.role,
            jira_account = EXCLUDED.jira_account
        RETURNING id_user;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute(query, (name, telegram_username, tg_id, jira_account, role))
            user_id = cursor.fetchone()[0]
            connection.commit()
            logger.info(f"✅ Пользователь зарегистрирован: {name} (tg_id: {tg_id}, роль: {role})")
            return True
        except Exception as e:
            logger.error(f"Ошибка регистрации пользователя: {e}")
            connection.rollback()
            return False
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_users_by_role(role):
        """Получение пользователей по конкретной роли (например, 'worker' или 'senior_worker')"""
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
        """Получение пользователей по категории ролей (worker или ceo)"""
        # Получаем все роли этой категории из конфига
        from config.roles_config import ROLE_CATEGORIES

        if role_category not in ROLE_CATEGORIES:
            return []

        role_types = list(ROLE_CATEGORIES[role_category]['subtypes'].keys())

        if not role_types:
            return []

        # Создаем строку с плейсхолдерами для IN запроса
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
        """Получение всех пользователей с tg_id"""
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


# Остальные классы остаются без изменений
class SurveyModel:
    @staticmethod
    def create_survey(survey_data):
        """Создание нового опроса в БД"""
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
        """Получение активных опросов"""
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
        """Получение опросов для определенной роли"""
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

    @staticmethod
    def get_surveys_with_response_status(user_id, role):
        """Получение опросов с информацией о том, отвечал ли пользователь"""
        # Получаем опросы для роли
        surveys_for_role = SurveyModel.get_surveys_for_role(role)

        # Получаем опросы для всех
        surveys_for_all = SurveyModel.get_surveys_for_role(None)

        # Объединяем и удаляем дубликаты
        all_surveys = {}
        for survey in surveys_for_role + surveys_for_all:
            if survey['id_survey'] not in all_surveys:
                all_surveys[survey['id_survey']] = survey

        # Проверяем ответы пользователя
        result = []
        for survey in all_surveys.values():
            response = ResponseModel.get_user_response(survey['id_survey'], user_id)
            survey['has_responded'] = response is not None
            if response:
                survey['user_response'] = response['answer']
            result.append(survey)

        return result


class ResponseModel:
    @staticmethod
    def save_response(response_data):
        """Сохранение ответа на опрос"""
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


class ResponseModel:
    """Модель ответов на опросы"""

    @staticmethod
    def save_response(response_data):
        """Сохранение ответа на опрос"""
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


class BlockerModel:
    """Модель блокеров (проблем)"""

    @staticmethod
    def get_blockers_by_date(date):
        """Получение блокеров за определенную дату"""
        query = '''
        SELECT b.*, u.name as user_name, r.answer, s.datetime as survey_date
        FROM blockers b
        JOIN responses r ON b.id_response = r.id_response
        JOIN surveys s ON r.id_survey = s.id_survey
        JOIN users u ON b.id_user = u.id_user
        WHERE DATE(s.datetime) = %s
        ORDER BY b.critical DESC;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (date,))
            blockers = cursor.fetchall()
            return [dict(blocker) for blocker in blockers]
        except Exception as e:
            logger.error(f"Ошибка получения блокеров: {e}")
            return []
        finally:
            cursor.close()
            connection.close()


class DailyDigestModel:
    """Модель ежедневных дайджестов"""

    @staticmethod
    def get_daily_digest(date):
        """Получение ежедневного дайджеста за дату"""
        query = '''
        SELECT * FROM daily_digest 
        WHERE datetime = %s
        ORDER BY id_daily;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (date,))
            digests = cursor.fetchall()
            return [dict(digest) for digest in digests]
        except Exception as e:
            logger.error(f"Ошибка получения ежедневного дайджеста: {e}")
            return []
        finally:
            cursor.close()
            connection.close()


class WeekDigestModel:
    """Модель еженедельных дайджестов"""

    @staticmethod
    def get_week_digest(start_date, end_date):
        """Получение еженедельных дайджестов за период"""
        query = '''
        SELECT * FROM week_digest 
        WHERE datetime BETWEEN %s AND %s
        ORDER BY datetime;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (start_date, end_date))
            digests = cursor.fetchall()
            return [dict(digest) for digest in digests]
        except Exception as e:
            logger.error(f"Ошибка получения еженедельного дайджеста: {e}")
            return []
        finally:
            cursor.close()
            connection.close()