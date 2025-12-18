import logging
from datetime import datetime, timezone
from tg_bot.database.connection import db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class ReminderModel:
    """Модель для отслеживания напоминаний о непройденных опросах"""

    @staticmethod
    def create_reminder(survey_id: int, user_id: int, reminder_stage: int, next_reminder_time: datetime,
                        survey_time: datetime = None):
        """Создание записи о напоминании"""
        # Нормализуем время - используем UTC
        if survey_time is None:
            survey_time = datetime.now(timezone.utc)
        elif survey_time.tzinfo is None:
            # Если время без часового пояса, считаем что это UTC
            survey_time = survey_time.replace(tzinfo=timezone.utc)

        # То же для next_reminder_time
        if next_reminder_time.tzinfo is None:
            next_reminder_time = next_reminder_time.replace(tzinfo=timezone.utc)

        query = '''
            INSERT INTO reminders 
            (survey_id, user_id, reminder_stage, next_reminder_time, status, created_at)
            VALUES (%s, %s, %s, %s, 'pending', %s)
            ON CONFLICT (survey_id, user_id, reminder_stage) 
            DO UPDATE SET next_reminder_time = EXCLUDED.next_reminder_time,
                         status = EXCLUDED.status,
                         created_at = EXCLUDED.created_at
            RETURNING id;
            '''

        connection = db_connection.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor()
            cursor.execute(query, (survey_id, user_id, reminder_stage, next_reminder_time, survey_time))
            reminder_id = cursor.fetchone()[0]
            connection.commit()
            logger.info(f"Напоминание создано: опрос #{survey_id}, пользователь #{user_id}, этап {reminder_stage}")
            logger.info(f"  Время отправки опроса: {survey_time}")
            logger.info(f"  Время напоминания: {next_reminder_time}")
            logger.info(f"  Интервал: {(next_reminder_time - survey_time).total_seconds()} секунд")
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
            SELECT 
                r.*, 
                u.tg_id, 
                s.question, 
                s.datetime as survey_time,
                s.state as survey_state,
                -- Изменено: добавляем 3 часа к времени БД для сравнения
                EXTRACT(epoch FROM (NOW() AT TIME ZONE 'UTC' + INTERVAL '3 hours' - r.next_reminder_time)) as seconds_late,
                r.next_reminder_time as raw_time,
                NOW() AT TIME ZONE 'UTC' + INTERVAL '3 hours' as db_now_adjusted,
                -- Основное условие: добавляем 3 часа к времени БД
                (r.next_reminder_time <= NOW() AT TIME ZONE 'UTC' + INTERVAL '3 hours') as is_due_adjusted
            FROM reminders r
            JOIN users u ON r.user_id = u.id_user
            JOIN surveys s ON r.survey_id = s.id_survey
            WHERE r.status = 'pending' 
            -- ИЗМЕНЕНО: сравниваем с временем БД + 3 часа
            AND r.next_reminder_time <= NOW() AT TIME ZONE 'UTC' + INTERVAL '3 hours'
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

            logger.info(f"Основной запрос вернул {len(reminders)} напоминаний для отправки")

            if reminders:
                for reminder in reminders[:3]:  # Первые 3 для логов
                    logger.info(f"НАЙДЕНО: ID={reminder['id']}, Survey=#{reminder['survey_id']}")
                    logger.info(f"   Время напоминания: {reminder['raw_time']}")
                    logger.info(f"   Время БД (скорректированное): {reminder['db_now_adjusted']}")
                    logger.info(f"   Просрочено на: {reminder['seconds_late']:.0f} сек")
                    logger.info(f"   is_due_adjusted: {reminder['is_due_adjusted']}")

            return [dict(reminder) for reminder in reminders]
        except Exception as e:
            logger.error(f"Ошибка получения напоминаний: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _run_diagnostics():
        """Диагностика системы напоминаний"""
        try:
            logger.info("🩺 ЗАПУСК ДИАГНОСТИКИ")

            # 1. Проверяем разницу времени
            ReminderModel._check_time_difference()

            # 2. Проверяем все pending напоминания с деталями
            ReminderModel._check_all_pending_with_details()

        except Exception as e:
            logger.error(f"Ошибка диагностики: {e}")

    @staticmethod
    def _check_time_difference():
        """Проверка разницы времени"""
        try:
            connection = db_connection.get_connection()
            if not connection:
                return

            cursor = connection.cursor(cursor_factory=RealDictCursor)

            # Проверяем текущее время в БД
            cursor.execute("""
                SELECT 
                    NOW() as db_now,
                    CURRENT_TIMESTAMP as current_ts,
                    LOCALTIMESTAMP as local_ts,
                    EXTRACT(epoch FROM NOW()) as epoch_now
            """)
            time_info = cursor.fetchone()

            logger.info("ВРЕМЯ:")
            logger.info(f"   БД NOW(): {time_info['db_now']}")
            logger.info(f"   БД CURRENT_TIMESTAMP: {time_info['current_ts']}")
            logger.info(f"   БД LOCALTIMESTAMP: {time_info['local_ts']}")
            logger.info(f"   Python UTC: {datetime.now(timezone.utc)}")
            logger.info(f"   Python Local: {datetime.now()}")

            cursor.close()
            connection.close()

        except Exception as e:
            logger.error(f"Ошибка проверки времени: {e}")

    @staticmethod
    def _check_all_pending_with_details():
        """Проверка всех pending напоминаний с деталями"""
        try:
            connection = db_connection.get_connection()
            if not connection:
                return

            cursor = connection.cursor(cursor_factory=RealDictCursor)

            # Получаем ВСЕ pending напоминания с деталями
            query = '''
            SELECT 
                r.id,
                r.survey_id,
                r.user_id,
                r.reminder_stage,
                r.next_reminder_time,
                r.created_at,
                r.status,
                s.state as survey_state,
                u.tg_id,
                EXTRACT(epoch FROM (NOW() - r.next_reminder_time)) as seconds_diff,
                (r.next_reminder_time <= NOW()) as is_past,
                (s.state = 'active') as is_active,
                (u.tg_id IS NOT NULL) as has_tg
            FROM reminders r
            LEFT JOIN surveys s ON r.survey_id = s.id_survey
            LEFT JOIN users u ON r.user_id = u.id_user
            WHERE r.status = 'pending'
            ORDER BY r.next_reminder_time ASC
            LIMIT 20;
            '''

            cursor.execute(query)
            reminders = cursor.fetchall()

            logger.info("PENDING НАПОМИНАНИЯ (первые 20):")

            for i, reminder in enumerate(reminders):
                status = "ПРОШЛО" if reminder['is_past'] else "⏳ БУДУЩЕЕ"
                logger.info(
                    f"{i + 1}. ID={reminder['id']}, Survey=#{reminder['survey_id']}, Stage={reminder['reminder_stage']}")
                logger.info(f"   Время: {reminder['next_reminder_time']} ({status})")
                logger.info(f"   Разница: {reminder['seconds_diff']:.0f} сек")
                logger.info(f"   Опрос активен: {reminder['is_active']} (статус: {reminder['survey_state']})")
                logger.info(f"   TG ID: {reminder['tg_id']} (есть: {reminder['has_tg']})")

                if reminder['is_past'] and reminder['is_active'] and reminder['has_tg']:
                    logger.info(f"   ЭТО НАПОМИНАНИЕ ДОЛЖНО БЫТЬ ОТПРАВЛЕНО!")

            cursor.close()
            connection.close()

        except Exception as e:
            logger.error(f"Ошибка проверки напоминаний: {e}")

    @staticmethod
    def mark_reminder_sent(reminder_id: int):
        """Пометка напоминания как отправленного (без sent_at)"""
        query = '''
        UPDATE reminders 
        SET status = 'sent'
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
            logger.error(f"Ошибка обновления напоминания #{reminder_id}: {e}")
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
        """Отмена всех напоминаний для пользователя по опросу (без cancelled_at)"""
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

    @staticmethod
    def fix_timezone_issue():
        """Исправление проблемы с часовыми поясами (для отладки)"""
        try:
            connection = db_connection.get_connection()
            if not connection:
                return

            cursor = connection.cursor(cursor_factory=RealDictCursor)

            # Смотрим напоминания, которые должны были отправиться
            query = '''
            SELECT id, next_reminder_time, created_at,
                   EXTRACT(epoch FROM (NOW() - next_reminder_time)) as diff_seconds,
                   next_reminder_time AT TIME ZONE 'UTC' as utc_time,
                   next_reminder_time AT TIME ZONE 'Europe/Moscow' as moscow_time
            FROM reminders 
            WHERE status = 'pending'
            AND EXTRACT(epoch FROM (NOW() - next_reminder_time)) BETWEEN -3600 AND 3600
            ORDER BY ABS(EXTRACT(epoch FROM (NOW() - next_reminder_time))) ASC
            LIMIT 10;
            '''

            cursor.execute(query)
            near_reminders = cursor.fetchall()

            logger.info("БЛИЖАЙШИЕ НАПОМИНАНИЯ (±1 час):")

            for reminder in near_reminders:
                diff = reminder['diff_seconds']
                if diff > 0:
                    status = f"ПРОСРОЧЕНО на {diff:.0f} сек"
                elif diff < 0:
                    status = f"ЧЕРЕЗ {-diff:.0f} сек"
                else:
                    status = "СЕЙЧАС"

                logger.info(f"ID={reminder['id']}: {reminder['next_reminder_time']}")
                logger.info(f"   {status}")
                logger.info(f"   UTC: {reminder['utc_time']}")
                logger.info(f"   Moscow: {reminder['moscow_time']}")

            cursor.close()
            connection.close()

        except Exception as e:
            logger.error(f"Ошибка исправления часовых поясов: {e}")