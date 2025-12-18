import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Set
from telegram import Bot

from tg_bot.config.constants import REMINDER_INTERVALS, SCHEDULER_CHECK_INTERVAL
from tg_bot.config.roles_config import get_role_category
from tg_bot.database.connection import db_connection
from tg_bot.database.models import SurveyModel, UserModel
from tg_bot.config.texts import get_role_display_name
from tg_bot.database.reminder_models import ReminderModel

logger = logging.getLogger(__name__)


class SurveyScheduler:
    """Планировщик для отправки опросов и напоминаний"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduled_tasks: Dict[int, asyncio.Task] = {}
        self.sent_surveys_cache: Set[int] = set()

    async def start(self):
        """Запуск планировщика"""
        logger.info("🚀 Запуск планировщика опросов и напоминаний...")

        # Загружаем активные опросы из БД и планируем их отправку
        await self.schedule_existing_surveys()

        # Запускаем периодическую проверку новых опросов и напоминаний
        asyncio.create_task(self.periodic_check())

    async def schedule_existing_surveys(self):
        """Планирование существующих опросов из БД - ПРИОРИТЕТ ПО СТАТУСУ"""
        surveys = SurveyModel.get_active_surveys()

        logger.info(f"📋 Загружено {len(surveys)} активных опросов из БД")

        for survey in surveys:
            survey_id = survey['id_survey']
            survey_time = survey['datetime']

            # 1. Проверяем, есть ли отправленные напоминания
            has_sent_reminders = await self._check_if_survey_was_sent(survey_id)

            if has_sent_reminders:
                # Есть отправленные напоминания - опрос уже отправлен
                if survey_id not in self.sent_surveys_cache:
                    self.sent_surveys_cache.add(survey_id)
                    logger.info(f"✅ Опрос #{survey_id} уже был отправлен (есть sent напоминания)")
                continue

            # 2. Проверяем, есть ли pending напоминания
            has_pending_reminders = await self._check_if_survey_has_pending_reminders(survey_id)

            if has_pending_reminders:
                # Есть pending напоминания - НУЖНО ОТПРАВИТЬ!
                if survey_time > datetime.now():
                    logger.info(f"🚨 ОПРОС #{survey_id}: ЕСТЬ PENDING НАПОМИНАНИЯ, время еще не наступило")
                    # Планируем проверку времени (напоминания сами отправятся когда время придет)
                else:
                    logger.info(f"🚨 ОПРОС #{survey_id}: ЕСТЬ PENDING НАПОМИНАНИЯ, время УЖЕ прошло!")
                    logger.info(f"   Напоминания будут отправлены при следующей проверке планировщиком")
                continue

            # 3. Нет никаких напоминаний - опрос НЕ отправлялся
            if survey_time > datetime.now():
                # Время еще не наступило - планируем
                await self.schedule_survey(survey_id, survey_time)
                logger.info(f"📅 Опрос #{survey_id} запланирован на {survey_time}")
            else:
                # Время уже прошло - отправляем СРАЗУ
                logger.info(f"🚀 Опрос #{survey_id} время прошло, отправляю СЕЙЧАС...")
                await self.send_survey_now(survey_id, survey_time)

    async def _check_if_survey_was_sent(self, survey_id: int) -> bool:
        """Проверка, был ли опрос отправлен (есть ли отправленные напоминания)"""
        try:
            connection = db_connection.get_connection()
            if not connection:
                return False

            cursor = connection.cursor()
            # Проверяем, есть ли ХОТЯ БЫ ОДНО отправленное напоминание для этого опроса
            query = "SELECT COUNT(*) as count FROM reminders WHERE survey_id = %s AND status = 'sent'"
            cursor.execute(query, (survey_id,))
            count = cursor.fetchone()[0]
            cursor.close()
            connection.close()

            # Если есть хотя бы одно отправленное напоминание - опрос считается отправленным
            return count > 0

        except Exception as e:
            logger.error(f"❌ Ошибка проверки отправленных напоминаний для опроса #{survey_id}: {e}")
            return False

    async def _check_if_survey_has_pending_reminders(self, survey_id: int) -> bool:
        """Проверка, есть ли pending напоминания для опроса"""
        try:
            connection = db_connection.get_connection()
            if not connection:
                return False

            cursor = connection.cursor()
            # Проверяем, есть ли pending напоминания
            query = "SELECT COUNT(*) as count FROM reminders WHERE survey_id = %s AND status = 'pending'"
            cursor.execute(query, (survey_id,))
            count = cursor.fetchone()[0]
            cursor.close()
            connection.close()

            # Если есть pending напоминания - их нужно отправить
            return count > 0

        except Exception as e:
            logger.error(f"❌ Ошибка проверки pending напоминаний для опроса #{survey_id}: {e}")
            return False

    async def create_reminders_for_survey(self, survey_id: int, survey_time: datetime):
        """Создание напоминаний для всех пользователей опроса"""
        try:
            from datetime import timezone

            # Получаем опрос
            surveys = SurveyModel.get_active_surveys()
            survey = next((s for s in surveys if s['id_survey'] == survey_id), None)

            if not survey:
                logger.error(f"❌ Опрос #{survey_id} не найден")
                return

            # Получаем пользователей для этого опроса
            users = await self.get_target_users(survey)

            # Нормализуем время опроса в UTC
            if survey_time.tzinfo is None:
                # Если время без часового пояса, считаем что это локальное время сервера
                # и конвертируем в UTC
                survey_time_utc = survey_time.astimezone(timezone.utc) if survey_time.tzinfo else survey_time.replace(
                    tzinfo=timezone.utc)
            else:
                survey_time_utc = survey_time.astimezone(timezone.utc)

            logger.info(f"📝 Создаем напоминания для опроса #{survey_id}")
            logger.info(f"   Время опроса (local): {survey_time}")
            logger.info(f"   Время опроса (UTC): {survey_time_utc}")

            reminders_created = 0
            users_without_tg = 0

            for user in users:
                user_id = user['id_user']
                tg_id = user.get('tg_id')

                if not tg_id:
                    users_without_tg += 1
                    continue

                # Проверяем, не ответил ли уже пользователь
                has_response = ReminderModel.check_user_response(survey_id, user_id)

                if not has_response:
                    # Создаем напоминания для каждого этапа из констант
                    for stage in sorted(REMINDER_INTERVALS.keys()):
                        interval_seconds = REMINDER_INTERVALS[stage]
                        reminder_time = survey_time_utc + timedelta(seconds=interval_seconds)

                        success = ReminderModel.create_reminder(
                            survey_id=survey_id,
                            user_id=user_id,
                            reminder_stage=stage,
                            next_reminder_time=reminder_time,
                            survey_time=survey_time_utc
                        )

                        if success:
                            reminders_created += 1
                            logger.debug(f"   Создано напоминание этап {stage} на {reminder_time}")

            logger.info(f"✅ Создано {reminders_created} напоминаний для опроса #{survey_id}")
            if users_without_tg > 0:
                logger.warning(f"⚠️  Пропущено {users_without_tg} пользователей без TG ID")

        except Exception as e:
            logger.error(f"❌ Ошибка создания напоминаний для опроса #{survey_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def check_and_send_reminders(self):
        """Проверка и отправка напоминаний"""
        try:
            logger.info("🔍 ПРОВЕРКА НАПОМИНАНИЙ...")

            # Получаем все готовые к отправке напоминания
            pending_reminders = ReminderModel.get_pending_reminders()
            logger.info(f"📊 Найдено {len(pending_reminders)} напоминаний для отправки")

            sent_count = 0
            skipped_count = 0

            for reminder in pending_reminders:
                reminder_id = reminder['id']
                survey_id = reminder['survey_id']
                user_id = reminder['user_id']
                tg_id = reminder['tg_id']
                stage = reminder['reminder_stage']

                logger.info(
                    f"📨 Обрабатываю напоминание #{reminder_id} для пользователя {tg_id} (опрос #{survey_id}, этап {stage})")

                # Двойная проверка: отвечал ли пользователь
                has_response = ReminderModel.check_user_response(survey_id, user_id)

                if has_response:
                    logger.info(f"✅ Пользователь {tg_id} уже ответил на опрос #{survey_id}, отменяю напоминания")
                    ReminderModel.cancel_user_reminders(survey_id, user_id)
                    skipped_count += 1
                    continue

                # Отправляем напоминание
                try:
                    await self.send_reminder_to_user(reminder)

                    # Помечаем как отправленное
                    ReminderModel.mark_reminder_sent(reminder_id)
                    sent_count += 1

                    logger.info(f"✅ Напоминание отправлено: опрос #{survey_id}, пользователь #{user_id}, этап {stage}")

                except Exception as e:
                    logger.error(f"❌ Ошибка отправки напоминания #{reminder_id}: {e}")

            if sent_count > 0:
                logger.info(f"✅ Отправлено {sent_count} напоминаний, пропущено {skipped_count}")
            elif pending_reminders:
                logger.warning(
                    f"⚠️  НАПОМИНАНИИ ЕСТЬ, НО НЕ ОТПРАВЛЕНЫ: найдено {len(pending_reminders)}, отправлено 0")
            else:
                logger.info(f"ℹ️  Нет напоминаний для отправки")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминаний: {e}")
            logger.error(traceback.format_exc())

    async def _run_extra_diagnostics(self):
        """Дополнительная диагностика"""
        try:
            # Принудительная проверка просроченных напоминаний
            overdue_reminders = ReminderModel.force_send_overdue_reminders()

            if overdue_reminders:
                logger.warning(f"⚠️  ОБНАРУЖЕНЫ ПРОСРОЧЕННЫЕ НАПОМИНАНИЯ: {len(overdue_reminders)} шт.")

                # Проверяем статусы опросов
                survey_ids = set(r['survey_id'] for r in overdue_reminders)
                logger.info(f"   Опросы с просроченными напоминаниями: {survey_ids}")

        except Exception as e:
            logger.error(f"❌ Ошибка дополнительной диагностики: {e}")

    async def send_reminder_to_user(self, reminder):
        """Отправка напоминания конкретному пользователю"""
        try:
            tg_id = reminder['tg_id']
            survey_id = reminder['survey_id']
            stage = reminder['reminder_stage']
            question = reminder['question']
            survey_time = reminder['survey_time']

            # Форматируем сообщение с учетом этапа напоминания
            stage_texts = {
                1: "Первое напоминание об опросе",
                2: "Второе напоминание об опросе",
                3: "Финальное напоминание об опросе"
            }

            stage_text = stage_texts.get(stage, "Напоминание об опросе")

            message = (
                f"🔔 {stage_text}\n\n"
                f"Вопрос: {question}\n"
                f"Время опроса: {survey_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"ID опроса: {survey_id}\n\n"
                f"Пожалуйста, ответьте на опрос:\n"
                f"/response\n\n"
                f"После выберите этот опрос из списка."
            )

            await self.bot.send_message(
                chat_id=tg_id,
                text=message
            )

            logger.info(f"📤 Напоминание отправлено пользователю {tg_id} (опрос #{survey_id}, этап {stage})")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминания пользователю {tg_id}: {e}")
            raise

    async def schedule_survey(self, survey_id: int, send_time: datetime):
        """Планирование отправки опроса"""
        # Отменяем существующую задачу, если есть
        if survey_id in self.scheduled_tasks:
            self.scheduled_tasks[survey_id].cancel()
            logger.info(f"🔄 Отменена предыдущая задача для опроса #{survey_id}")

        # Вычисляем задержку в секундах
        now = datetime.now()
        delay = (send_time - now).total_seconds()

        if delay > 0:
            # Создаем асинхронную задачу
            task = asyncio.create_task(
                self.send_survey_delayed(survey_id, delay, send_time)
            )
            self.scheduled_tasks[survey_id] = task
            logger.info(f"📅 Опрос #{survey_id} запланирован через {delay:.0f} секунд ({delay / 3600:.1f} часов)")
            return True
        else:
            # Время уже наступило, отправляем немедленно
            logger.info(f"⏰ Время опроса #{survey_id} уже наступило, отправляю немедленно")
            await self.send_survey_now(survey_id, send_time)
            return False

    async def send_survey_delayed(self, survey_id: int, delay: float, send_time: datetime):
        """Отправка опроса с задержкой"""
        try:
            # Ждем указанное время
            logger.info(f"⏳ Ожидание {delay:.0f} секунд для опроса #{survey_id}")
            await asyncio.sleep(delay)

            # Отправляем опрос
            await self.send_survey_now(survey_id, send_time)

            # Удаляем задачу из списка
            if survey_id in self.scheduled_tasks:
                del self.scheduled_tasks[survey_id]

        except asyncio.CancelledError:
            logger.info(f"⏹️ Отправка опроса #{survey_id} отменена")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки опроса #{survey_id}: {e}")

    async def send_survey_now(self, survey_id: int, send_time: datetime = None):
        """Немедленная отправка опроса пользователям"""
        try:
            # Получаем данные опроса
            surveys = SurveyModel.get_active_surveys()
            survey = next((s for s in surveys if s['id_survey'] == survey_id), None)

            if not survey:
                logger.error(f"❌ Опрос #{survey_id} не найден")
                return

            # Если время не передано, используем время из БД
            if send_time is None:
                send_time = survey['datetime']

            # Получаем пользователей для этого опроса
            users = await self.get_target_users(survey)

            if not users:
                logger.warning(f"⚠️ Нет пользователей для опроса #{survey_id}")
                return

            # Отправляем опрос каждому пользователю
            sent_count = 0
            failed_count = 0

            for user in users:
                try:
                    await self.send_survey_to_user(user, survey)
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.error(
                        f"❌ Ошибка отправки опроса #{survey_id} пользователю {user.get('user_name', 'Unknown')}: {e}")

            # Помечаем опрос как отправленный в кэше
            self.sent_surveys_cache.add(survey_id)

            # СОЗДАЕМ НАПОМИНАНИЯ
            await self.create_reminders_for_survey(survey_id, send_time)

            logger.info(f"✅ ОПРОС ОТПРАВЛЕН: #{survey_id} - отправлено {sent_count}, ошибок {failed_count}")

        except Exception as e:
            logger.error(f"❌ Ошибка при отправке опроса #{survey_id}: {e}")
            logger.error(f"Трассировка ошибки: {traceback.format_exc()}")

    async def get_target_users(self, survey) -> List[Dict]:
        """Получение целевых пользователей для опроса"""

        if survey['role'] is None:
            # Опрос для всех
            users = UserModel.get_all_users_with_tg_id()
            logger.info(f"👥 Опрос для всех пользователей: найдено {len(users)} пользователей")
            return users
        else:
            # Определяем категорию роли из опроса
            role_category = get_role_category(survey['role'])

            if role_category:
                # Если опрос для конкретной роли, получаем пользователей по конкретной роли
                users = UserModel.get_users_by_role(survey['role'])
                logger.info(f"👥 Опрос для роли '{survey['role']}': найдено {len(users)} пользователей")
                return users
            else:
                logger.error(f"❌ Неизвестная роль в опросе: {survey['role']}")
                return []

    async def send_survey_to_user(self, user: Dict, survey: Dict):
        """Отправка опроса конкретному пользователю по tg_id"""
        tg_id = user['tg_id']

        if not tg_id:
            logger.warning(f"⚠️ User {user.get('user_name', 'Unknown')} has no tg_id")
            return

        # Формируем сообщение
        role_display = get_role_display_name(user['role'])

        # Определяем, для кого опрос
        target = survey['role'] if survey['role'] else "все пользователи"

        # Используем user_name вместо name
        user_name = user.get('user_name', 'Неизвестный пользователь')

        message = (
            f"📊 Новый опрос от руководителя!\n\n"
            f"❓ Вопрос: {survey['question']}\n"
            f"👤 Ваша роль: {role_display}\n"
            f"🎯 Аудитория: {target}\n"
            f"📅 Дата: {survey['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
            f"🆔 ID опроса: {survey['id_survey']}\n\n"
            f"Чтобы ответить, используйте команду:\n"
            f"➡️  /response\n\n"
            f"Затем выберите этот опрос из списка."
        )

        # Отправляем сообщение
        try:
            await self.bot.send_message(
                chat_id=tg_id,
                text=message
            )
            logger.debug(f"✅ Survey #{survey['id_survey']} sent to user {user_name} (tg_id: {tg_id})")
        except Exception as e:
            logger.error(f"❌ Error sending to user {user_name} (tg_id: {tg_id}): {e}")
            raise

    async def periodic_check(self):
        """Периодическая проверка новых опросов и напоминаний"""
        check_count = 0

        while True:
            try:
                check_count += 1
                logger.info(f"🔄 ЦИКЛ ПРОВЕРКИ #{check_count}")

                # Проверяем каждые 30 секунд
                await asyncio.sleep(SCHEDULER_CHECK_INTERVAL)

                # 1. Проверяем новые опросы
                surveys = SurveyModel.get_active_surveys()
                current_survey_ids = {s['id_survey'] for s in surveys}

                # Удаляем задачи для завершенных опросов
                for survey_id in list(self.scheduled_tasks.keys()):
                    if survey_id not in current_survey_ids:
                        if survey_id in self.scheduled_tasks:
                            self.scheduled_tasks[survey_id].cancel()
                            del self.scheduled_tasks[survey_id]
                            logger.info(f"🗑️ Задача для опроса #{survey_id} удалена (опрос не активен)")

                # Добавляем новые опросы (те, которые были созданы через sendsurvey)
                for survey in surveys:
                    survey_id = survey['id_survey']
                    survey_time = survey['datetime']

                    # Если опрос еще не в планировщике и время в будущем
                    if survey_id not in self.scheduled_tasks and survey_id not in self.sent_surveys_cache and survey_time > datetime.now():
                        logger.info(f"🆕 Обнаружен новый опрос #{survey_id}, планирую отправку на {survey_time}")
                        await self.schedule_survey(survey_id, survey_time)

                # 2. Проверяем и отправляем напоминания
                await self.check_and_send_reminders()

                logger.info(f"✅ ЦИКЛ ПРОВЕРКИ #{check_count} завершен")

            except Exception as e:
                logger.error(f"❌ Ошибка в periodic_check (цикл #{check_count}): {e}")
                logger.error(traceback.format_exc())

    async def add_new_survey(self, survey_id: int, send_time: datetime):
        """Добавление нового опроса в планировщик"""
        now = datetime.now()

        logger.info(f"➕ ДОБАВЛЕН НОВЫЙ ОПРОС: #{survey_id} на {send_time}")

        # Если время уже прошло, отправляем немедленно
        if send_time <= now:
            logger.info(f"⏰ Время опроса #{survey_id} уже наступило, отправляю немедленно")
            await self.send_survey_now(survey_id)
        else:
            # Иначе планируем на будущее
            delay = (send_time - now).total_seconds()
            logger.info(f"📅 Опрос #{survey_id} запланирован через {delay:.0f} секунд")
            await self.schedule_survey(survey_id, send_time)

    async def stop(self):
        """Остановка планировщика"""
        logger.info("🛑 ОСТАНОВКА ПЛАНИРОВЩИКА...")

        # Отменяем все задачи
        for survey_id, task in list(self.scheduled_tasks.items()):
            task.cancel()
            logger.info(f"⏹️ Отменена задача для опроса #{survey_id}")

        self.scheduled_tasks.clear()
        logger.info("✅ Планировщик опросов остановлен")