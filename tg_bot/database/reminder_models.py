import logging
from datetime import datetime
from tg_bot.database.connection import db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class ReminderModel:
    """Модель для отслеживания напоминаний о непройденных опросах"""

    @staticmethod
    def create_reminder(survey_id: int, user_id: int, reminder_stage: int, next_reminder_time: datetime):
        """Создание записи о напоминании"""
        query = '''
        INSERT INTO reminders 
        (survey_id, user_id, reminder_stage, next_reminder_time, status)
        VALUES (%s, %s, %s, %s, 'pending')
        ON CONFLICT (survey_id, user_id, reminder_stage) 
        DO UPDATE SET next_reminder_time = EXCLUDED.next_reminder_time,
                     status = EXCLUDED.status
        RETURNING id;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor()
            cursor.execute(query, (survey_id, user_id, reminder_stage, next_reminder_time))
            reminder_id = cursor.fetchone()[0]
            connection.commit()
            logger.info(f"Напоминание создано: опрос #{survey_id}, пользователь #{user_id}, этап {reminder_stage}")
            return reminder_id
        except Exception as e:
            logger.error(f"Ошибка создания напоминания: {e}")
            connection.rollback()
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_pending_reminders():
        """Получение всех ожидающих напоминаний"""
        query = '''
        SELECT r.*, u.tg_id, s.question, s.datetime as survey_time
        FROM reminders r
        JOIN users u ON r.user_id = u.id_user
        JOIN surveys s ON r.survey_id = s.id_survey
        WHERE r.status = 'pending' 
        AND r.next_reminder_time <= NOW()
        AND s.state = 'active';
        '''

        connection = db_connection.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            reminders = cursor.fetchall()
            return [dict(reminder) for reminder in reminders]
        except Exception as e:
            logger.error(f"Ошибка получения напоминаний: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def mark_reminder_sent(reminder_id: int):
        """Пометка напоминания как отправленного"""
        query = '''
        UPDATE reminders 
        SET status = 'sent', sent_at = NOW()
        WHERE id = %s;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute(query, (reminder_id,))
            connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления напоминания: {e}")
            connection.rollback()
            return False
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def check_user_response(survey_id: int, user_id: int):
        """Проверка, ответил ли пользователь на опрос"""
        query = '''
        SELECT id_response FROM responses 
        WHERE id_survey = %s AND id_user = %s;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute(query, (survey_id, user_id))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Ошибка проверки ответа: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def cancel_user_reminders(survey_id: int, user_id: int):
        """Отмена всех напоминаний для пользователя по опросу"""
        query = '''
        UPDATE reminders 
        SET status = 'cancelled'
        WHERE survey_id = %s AND user_id = %s AND status = 'pending';
        '''

        connection = db_connection.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute(query, (survey_id, user_id))
            connection.commit()
            logger.info(f"Напоминания отменены: опрос #{survey_id}, пользователь #{user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка отмены напоминаний: {e}")
            connection.rollback()
            return False
        finally:
            cursor.close()
            connection.close()