import logging
from datetime import datetime
from tg_bot.database.connection import db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class ReminderModel:
    """Модель для отслеживания напоминаний о непройденных опросах"""

    @staticmethod
    def create_reminder(survey_id: int, user_id: int, reminder_stage: int, next_reminder_time: datetime):
        """Создание записи о напоминании - сохраняем время в UTC"""
        # Приводим время к UTC если нужно
        import pytz
        if next_reminder_time.tzinfo is None:
            # Если время без часового пояса, считаем его локальным и конвертируем в UTC
            next_reminder_time = pytz.UTC.localize(next_reminder_time)
        else:
            # Если время с часовым поясом, конвертируем в UTC
            next_reminder_time = next_reminder_time.astimezone(pytz.UTC)

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
            logger.info(
                f"Напоминание создано: опрос #{survey_id}, пользователь #{user_id}, этап {reminder_stage} на {next_reminder_time}")
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
        """Получение всех ожидающих напоминаний - сравниваем в UTC"""
        # Простой запрос - PostgreSQL сам сравнивает времена правильно
        query = '''
        SELECT r.*, u.tg_id, s.question, s.datetime as survey_time
        FROM reminders r
        JOIN users u ON r.user_id = u.id_user
        JOIN surveys s ON r.survey_id = s.id_survey
        WHERE r.status = 'pending' 
        AND r.next_reminder_time <= CURRENT_TIMESTAMP  -- Сравниваем в UTC
        AND s.state = 'active'
        ORDER BY r.next_reminder_time ASC;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            reminders = cursor.fetchall()

            logger.info(f"Найдено {len(reminders)} напоминаний, готовых к отправке")

            # Для отладки
            if reminders:
                import pytz
                from datetime import datetime
                utc_now = datetime.now(pytz.UTC)
                for reminder in reminders[:3]:  # Логируем первые 3
                    rt = reminder['next_reminder_time']
                    if rt.tzinfo is None:
                        rt = pytz.UTC.localize(rt)
                    logger.info(f"Напоминание #{reminder['id']} время: {rt} (сейчас UTC: {utc_now})")

            return [dict(reminder) for reminder in reminders]
        except Exception as e:
            logger.error(f"Ошибка получения напоминаний: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def debug_reminder_times():
        """Отладочный метод для проверки времен напоминаний"""
        query = '''
        SELECT 
            r.id,
            r.next_reminder_time as reminder_time,
            EXTRACT(epoch FROM r.next_reminder_time) as reminder_epoch,
            CURRENT_TIMESTAMP as db_now,
            EXTRACT(epoch FROM CURRENT_TIMESTAMP) as now_epoch
        FROM reminders r
        WHERE r.status = 'pending'
        ORDER BY r.next_reminder_time ASC
        LIMIT 5;
        '''

        connection = db_connection.get_connection()
        if not connection:
            return

        try:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            results = cursor.fetchall()

            logger.info("=== ОТЛАДКА ВРЕМЕНИ НАПОМИНАНИЙ ===")
            for row in results:
                logger.info(f"ID: {row['id']}")
                logger.info(f"  Время напоминания: {row['reminder_time']}")
                logger.info(f"  Epoch время: {row['reminder_epoch']}")
                logger.info(f"  Текущее время БД: {row['db_now']}")
                logger.info(f"  Epoch текущее: {row['now_epoch']}")
                logger.info(f"  Разница секунд: {float(row['now_epoch']) - float(row['reminder_epoch']):.2f}")
                logger.info(f"  Просрочено: {float(row['now_epoch']) > float(row['reminder_epoch'])}")
            logger.info("=== КОНЕЦ ОТЛАДКИ ===")

        except Exception as e:
            logger.error(f"Ошибка отладки времени: {e}")
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
            logger.info(f"Напоминание #{reminder_id} помечено как отправленное")
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
            result = cursor.fetchone() is not None
            if result:
                logger.info(f"Пользователь #{user_id} уже ответил на опрос #{survey_id}")
            return result
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
        SET status = 'cancelled', cancelled_at = NOW()
        WHERE survey_id = %s AND user_id = %s AND status = 'pending';
        '''

        connection = db_connection.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute(query, (survey_id, user_id))
            connection.commit()
            rows_affected = cursor.rowcount
            logger.info(
                f"Напоминания отменены: опрос #{survey_id}, пользователь #{user_id}, отменено {rows_affected} напоминаний")
            return True
        except Exception as e:
            logger.error(f"Ошибка отмены напоминаний: {e}")
            connection.rollback()
            return False
        finally:
            cursor.close()
            connection.close()