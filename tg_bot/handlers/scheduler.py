import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from telegram import Bot
from database.models import SurveyModel, UserModel

logger = logging.getLogger(__name__)


class SurveyScheduler:
    """Планировщик для отправки опросов"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduled_tasks: Dict[int, asyncio.Task] = {}

    async def start(self):
        """Запуск планировщика"""
        logger.info("🕐 Запуск планировщика опросов...")

        # Загружаем активные опросы из БД и планируем их
        await self.schedule_existing_surveys()

        # Запускаем периодическую проверку новых опросов
        await asyncio.create_task(self.periodic_check())

    async def schedule_existing_surveys(self):
        """Планирование существующих опросов из БД"""
        surveys = SurveyModel.get_active_surveys()

        for survey in surveys:
            survey_id = survey['id_survey']
            survey_time = survey['datetime']

            # Если время опроса в будущем, планируем его
            if survey_time > datetime.now():
                await self.schedule_survey(survey_id, survey_time)
                logger.info(f"Опрос #{survey_id} запланирован на {survey_time}")
            else:
                # Если время уже прошло, отправляем немедленно
                await self.send_survey_now(survey_id)
                logger.info(f"Опрос #{survey_id} отправлен немедленно (время прошло)")

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
            # Получаем опрос из БД
            surveys = SurveyModel.get_active_surveys()
            survey = next((s for s in surveys if s['id_survey'] == survey_id), None)

            if not survey:
                logger.error(f"Опрос #{survey_id} не найден")
                return

            # Получаем пользователей для отправки
            users = await self.get_target_users(survey)

            if not users:
                logger.warning(f"Нет пользователей для опроса #{survey_id}")
                return

            # Отправляем сообщение каждому пользователю
            sent_count = 0
            for user in users:
                try:
                    await self.send_survey_to_user(user, survey)
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        f"Ошибка отправки пользователю {user['name']} (chat_id: {user['tg_id']}): {e}")

            logger.info(f"Опрос #{survey_id} отправлен {sent_count} пользователям")

        except Exception as e:
            logger.error(f"Ошибка при отправке опроса #{survey_id}: {e}")

    async def get_target_users(self, survey) -> List[Dict]:
        """Получение целевых пользователей для опроса"""
        from config.roles_config import get_role_category

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
            logger.warning(f"User {user['name']} has no tg_id")
            return

        # Формируем сообщение
        from config.roles_config import get_role_display_name
        role_display = get_role_display_name(user['role'])

        # Определяем, для кого опрос
        target = survey['role'] if survey['role'] else "all users"

        message = (
            f"New survey from manager!\n\n"
            f"Question: {survey['question']}\n"
            f"Your role: {role_display}\n"
            f"Target audience: {target}\n"
            f"Date: {survey['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
            f"Survey ID: {survey['id_survey']}\n\n"
            f"To respond, use the command:\n"
            f"/response\n\n"
            f"Then select this survey from the list."
        )

        # Отправляем сообщение
        try:
            await self.bot.send_message(
                chat_id=tg_id,
                text=message
            )
            logger.info(f"✅ Survey #{survey['id_survey']} sent to user {user['name']} (tg_id: {tg_id})")
        except Exception as e:
            logger.error(f"❌ Error sending to user {user['name']} (tg_id: {tg_id}): {e}")


    async def periodic_check(self):
        """Периодическая проверка новых опросов"""
        while True:
            try:
                # Проверяем каждые 60 секунд
                await asyncio.sleep(60)

                # Получаем все активные опросы
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

            except Exception as e:
                logger.error(f"❌ Ошибка в periodic_check: {e}")

    async def add_new_survey(self, survey_id: int, send_time: datetime):
        """Добавление нового опроса в планировщик"""
        await self.schedule_survey(survey_id, send_time)

    async def stop(self):
        """Остановка планировщика"""
        # Отменяем все задачи
        for task in self.scheduled_tasks.values():
            task.cancel()

        self.scheduled_tasks.clear()
        logger.info("🛑 Планировщик опросов остановлен")
