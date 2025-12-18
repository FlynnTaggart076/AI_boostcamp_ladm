import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Set
from telegram import Bot

from tg_bot.config.roles_config import get_role_category
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

        # Настройки напоминаний
        self.reminder_stages = {
            1: timedelta(seconds=30),  # Через 30 секунд
            2: timedelta(minutes=1),  # Через 1 минуту (через 30 сек после первого)
        }

    async def start(self):
        """Запуск планировщика"""
        logger.info("Запуск планировщика опросов и напоминаний...")

        # Загружаем активные опросы из БД и планируем их
        await self.schedule_existing_surveys()

        # Запускаем периодическую проверку новых опросов и напоминаний
        await asyncio.create_task(self.periodic_check())

    async def schedule_existing_surveys(self):
        """Планирование существующих опросов из БД"""
        surveys = SurveyModel.get_active_surveys()

        for survey in surveys:
            survey_id = survey['id_survey']
            survey_time = survey['datetime']

            if survey_time > datetime.now():
                await self.schedule_survey(survey_id, survey_time)
                logger.info(f"Опрос #{survey_id} запланирован на {survey_time}")
            else:
                if survey_id not in self.sent_surveys_cache:
                    await self.send_survey_now(survey_id)
                    self.sent_surveys_cache.add(survey_id)
                    # Создаем напоминания для неотвеченных пользователей
                    await self.create_reminders_for_survey(survey_id)

    async def create_reminders_for_survey(self, survey_id: int):
        """Создание напоминаний для всех пользователей опроса"""
        try:
            # Получаем опрос
            surveys = SurveyModel.get_active_surveys()
            survey = next((s for s in surveys if s['id_survey'] == survey_id), None)

            if not survey:
                return

            # Получаем пользователей для этого опроса
            users = await self.get_target_users(survey)

            for user in users:
                user_id = user['id_user']

                # Проверяем, не ответил ли уже пользователь
                has_response = ReminderModel.check_user_response(survey_id, user_id)

                if not has_response:
                    # Создаем напоминания по расписанию
                    survey_time = survey['datetime']

                    for stage, delta in self.reminder_stages.items():
                        reminder_time = survey_time + delta

                        # Создаем напоминание только если время еще не прошло
                        if reminder_time > datetime.now():
                            ReminderModel.create_reminder(
                                survey_id=survey_id,
                                user_id=user_id,
                                reminder_stage=stage,
                                next_reminder_time=reminder_time
                            )

            logger.info(f"Напоминания созданы для опроса #{survey_id}")

        except Exception as e:
            logger.error(f"Ошибка создания напоминаний для опроса #{survey_id}: {e}")

    async def check_and_send_reminders(self):
        """Проверка и отправка напоминаний"""
        try:
            logger.info("🔍 Проверяю напоминания...")

            # Получаем все готовые к отправке напоминания
            pending_reminders = ReminderModel.get_pending_reminders()
            logger.info(f"📊 Найдено {len(pending_reminders)} напоминаний для отправки")

            for reminder in pending_reminders:
                reminder_id = reminder['id']
                survey_id = reminder['survey_id']
                user_id = reminder['user_id']
                tg_id = reminder['tg_id']

                logger.info(f"📨 Обрабатываю напоминание #{reminder_id} для пользователя {tg_id} (опрос #{survey_id})")

                # Двойная проверка: отвечал ли пользователь
                has_response = ReminderModel.check_user_response(survey_id, user_id)

                if has_response:
                    logger.info(f"✅ Пользователь {tg_id} уже ответил на опрос #{survey_id}, отменяю напоминания")
                    ReminderModel.cancel_user_reminders(survey_id, user_id)
                    continue

                # Отправляем напоминание
                await self.send_reminder_to_user(reminder)

                # Помечаем как отправленное
                ReminderModel.mark_reminder_sent(reminder_id)

                logger.info(
                    f"✅ Напоминание отправлено: опрос #{survey_id}, пользователь #{user_id}, этап {reminder['reminder_stage']}")

            logger.info("✅ Проверка напоминаний завершена")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминаний: {e}")
            logger.error(traceback.format_exc())

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
                1: "Напоминаем об опросе, отправленном час назад",
                2: "Второе напоминание об опросе",
                3: "Последнее напоминание об опросе"
            }

            stage_text = stage_texts.get(stage, "Напоминание об опросе")

            message = (
                f"🔔 {stage_text}\n\n"
                f"Вопрос: {question}\n"
                f"Дата опроса: {survey_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"ID опроса: {survey_id}\n\n"
                f"Пожалуйста, ответьте на опрос:\n"
                f"/response\n\n"
                f"После выберите этот опрос из списка."
            )

            await self.bot.send_message(
                chat_id=tg_id,
                text=message
            )

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")

    async def schedule_survey(self, survey_id: int, send_time: datetime):
        """Планирование отправки опроса"""
        # Отменяем существующую задачу, если есть
        if survey_id in self.scheduled_tasks:
            self.scheduled_tasks[survey_id].cancel()

        # Вычисляем задержку в секундах
        now = datetime.now()
        delay = (send_time - now).total_seconds()

        if delay > 0:
            # Создаем асинхронную задачу
            task = asyncio.create_task(
                self.send_survey_delayed(survey_id, delay)
            )
            self.scheduled_tasks[survey_id] = task
            return True
        else:
            # Время уже наступило, отправляем немедленно
            await self.send_survey_now(survey_id)
            return False

    async def send_survey_delayed(self, survey_id: int, delay: float):
        """Отправка опроса с задержкой"""
        try:
            # Ждем указанное время
            await asyncio.sleep(delay)

            # Отправляем опрос
            await self.send_survey_now(survey_id)

            # Удаляем задачу из списка
            if survey_id in self.scheduled_tasks:
                del self.scheduled_tasks[survey_id]

        except asyncio.CancelledError:
            logger.info(f"Отправка опроса #{survey_id} отменена")
        except Exception as e:
            logger.error(f"Ошибка отправки опроса #{survey_id}: {e}")

    async def send_survey_now(self, survey_id: int):
        """Немедленная отправка опроса пользователям"""
        try:
            # Получаем данные опроса
            surveys = SurveyModel.get_active_surveys()
            survey = next((s for s in surveys if s['id_survey'] == survey_id), None)

            if not survey:
                logger.error(f"Опрос #{survey_id} не найден")
                return

            # Получаем пользователей для этого опроса
            users = await self.get_target_users(survey)

            if not users:
                logger.warning(f"Нет пользователей для опроса #{survey_id}")
                return

            # Отправляем опрос каждому пользователю
            sent_count = 0
            for user in users:
                try:
                    await self.send_survey_to_user(user, survey)
                    sent_count += 1
                    logger.info(f"Опрос #{survey_id} отправлен пользователю {user.get('user_name', 'Unknown')}")
                except Exception as e:
                    logger.error(
                        f"Ошибка отправки опроса #{survey_id} пользователю {user.get('user_name', 'Unknown')}: {e}")

            # Помечаем опрос как отправленный в кэше
            self.sent_surveys_cache.add(survey_id)

            # Создаем напоминания для неотвеченных пользователей
            await self.create_reminders_for_survey(survey_id)

            logger.info(f"✅ Опрос #{survey_id} отправлен {sent_count} пользователям и созданы напоминания")

        except Exception as e:
            logger.error(f"Ошибка при отправке опроса #{survey_id}: {e}")
            logger.error(f"Трассировка ошибки: {traceback.format_exc()}")

    async def process_survey_response(self, survey_id: int, user_id: int):
        """Обработка ответа на опрос - отмена напоминаний"""
        ReminderModel.cancel_user_reminders(survey_id, user_id)

    async def get_target_users(self, survey) -> List[Dict]:
        """Получение целевых пользователей для опроса"""

        if survey['role'] is None:
            # Опрос для всех
            return UserModel.get_all_users_with_tg_id()
        else:
            # Определяем категорию роли из опроса
            role_category = get_role_category(survey['role'])

            if role_category:
                # Если опрос для конкретной роли, получаем пользователей по конкретной роли
                return UserModel.get_users_by_role(survey['role'])
            else:
                logger.error(f"Неизвестная роль в опросе: {survey['role']}")
                return []

    async def send_survey_to_user(self, user: Dict, survey: Dict):
        """Отправка опроса конкретному пользователю по tg_id"""
        tg_id = user['tg_id']

        if not tg_id:
            logger.warning(f"User {user.get('user_name', 'Unknown')} has no tg_id")
            return

        # Формируем сообщение
        role_display = get_role_display_name(user['role'])

        # Определяем, для кого опрос
        target = survey['role'] if survey['role'] else "все пользователи"

        # Используем user_name вместо name
        user_name = user.get('user_name', 'Неизвестный пользователь')

        message = (
            f"Новый опрос от руководителя!\n\n"
            f"Вопрос: {survey['question']}\n"
            f"Ваша роль: {role_display}\n"
            f"Аудитория: {target}\n"
            f"Дата: {survey['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
            f"ID опроса: {survey['id_survey']}\n\n"
            f"Чтобы ответить, используйте команду:\n"
            f"/response\n\n"
            f"Затем выберите этот опрос из списка."
        )

        # Отправляем сообщение
        try:
            await self.bot.send_message(
                chat_id=tg_id,
                text=message
            )
            logger.info(f"Survey #{survey['id_survey']} sent to user {user_name} (tg_id: {tg_id})")
        except Exception as e:
            logger.error(f"Error sending to user {user_name} (tg_id: {tg_id}): {e}")

    async def periodic_check(self):
        """Периодическая проверка новых опросов и напоминаний"""
        while True:
            try:
                # Проверяем каждые 30 секунд (как в первом файле, а не 60)
                await asyncio.sleep(30)

                # 1. Проверяем новые опросы
                surveys = SurveyModel.get_active_surveys()
                current_survey_ids = {s['id_survey'] for s in surveys}

                # Удаляем задачи для завершенных опросов
                for survey_id in list(self.scheduled_tasks.keys()):
                    if survey_id not in current_survey_ids:
                        if survey_id in self.scheduled_tasks:
                            self.scheduled_tasks[survey_id].cancel()
                            del self.scheduled_tasks[survey_id]

                # Добавляем новые опросы
                for survey in surveys:
                    survey_id = survey['id_survey']
                    survey_time = survey['datetime']

                    if survey_id not in self.scheduled_tasks and survey_time > datetime.now():
                        await self.schedule_survey(survey_id, survey_time)

                # 2. Проверяем и отправляем напоминания
                await self.check_and_send_reminders()

            except Exception as e:
                logger.error(f"❌ Ошибка в periodic_check: {e}")

    async def add_new_survey(self, survey_id: int, send_time: datetime):
        """Добавление нового опроса в планировщик"""
        now = datetime.now()

        # Если время уже прошло, отправляем немедленно
        if send_time <= now:
            await self.send_survey_now(survey_id)
        else:
            # Иначе планируем на будущее
            await self.schedule_survey(survey_id, send_time)

    async def stop(self):
        """Остановка планировщика"""
        # Отменяем все задачи
        for task in self.scheduled_tasks.values():
            task.cancel()

        self.scheduled_tasks.clear()
        logger.info("🛑 Планировщик опросов остановлен")