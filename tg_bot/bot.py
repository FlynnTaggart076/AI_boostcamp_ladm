import logging
import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

from tg_bot.config.roles_config import get_role_category
from tg_bot.config.settings import config
from tg_bot.config.constants import (
    AWAITING_PASSWORD,
    AWAITING_NAME,
    AWAITING_JIRA,
    AWAITING_ROLE
)
from tg_bot.handlers.auth_handlers import start_command, handle_message
from tg_bot.handlers.scheduler import SurveyScheduler

from tg_bot.config.texts import (
    HELP_TEXTS, format_profile, get_category_display, GENERAL_TEXTS, AUTH_TEXTS, SURVEY_TEXTS
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def cancel_command(update, context):
    """Отмена регистрации"""
    for key in ['awaiting_password', 'awaiting_name', 'awaiting_jira',
                'awaiting_role', 'user_name', 'jira_account']:
        context.user_data.pop(key, None)

    await update.message.reply_text(
        GENERAL_TEXTS['cancelled']
    )
    return ConversationHandler.END


async def help_command(update, context):
    """Обработчик команды /help с учетом категории ролей"""
    user_role = context.user_data.get('user_role')

    if not user_role:
        await update.message.reply_text(AUTH_TEXTS['not_authorized'])
        return

    from tg_bot.config.roles_config import get_role_category
    role_category = get_role_category(user_role)

    if not role_category:
        await update.message.reply_text(AUTH_TEXTS['unknown_role'])
        return

    if role_category == 'CEO':
        help_text = HELP_TEXTS['ceo']
    elif role_category == 'worker':
        help_text = HELP_TEXTS['worker']
    else:
        help_text = HELP_TEXTS['unknown_category']

    await update.message.reply_text(help_text)


async def profile_command(update, context):
    """Показать профиль пользователя"""
    user_role = context.user_data.get('user_role')
    user_name = context.user_data.get('user_name')
    jira_account = context.user_data.get('jira_account')

    if not user_role:
        await update.message.reply_text(AUTH_TEXTS['not_authorized'])
        return

    chat_id = update.effective_user.id

    await update.message.reply_text(
        format_profile(
            name=user_name,
            role=user_role,
            jira_account=jira_account,
            chat_id=chat_id
        )
    )


async def mysurveys_command(update, context):
    """Показать созданные опросы"""
    from tg_bot.config.roles_config import get_role_category

    user_role = context.user_data.get('user_role')
    role_category = get_role_category(user_role) if user_role else None

    if role_category != 'CEO':
        await update.message.reply_text(
            GENERAL_TEXTS['survey_view_permission']
        )
        return

    from tg_bot.database.models import SurveyModel
    surveys = SurveyModel.get_active_surveys()

    if not surveys:
        await update.message.reply_text(
            "Нет активных опросов."
        )
        return

    # Разбиваем список опросов на части по 4000 символов
    chunks = []
    current_chunk = SURVEY_TEXTS['surveys_list_title']
    chunk_count = 0

    for survey in surveys:
        role_display = survey['role'] if survey['role'] else 'все'
        survey_item = SURVEY_TEXTS['survey_item_format'].format(
            id=survey['id_survey'],
            question=survey['question'][:50] + ('...' if len(survey['question']) > 50 else ''),
            role=role_display,
            time=survey['datetime'].strftime('%d.%m.%Y %H:%M'),
            status=survey['state']
        )

        # Если добавление нового элемента превысит лимит, начинаем новый чанк
        if len(current_chunk) + len(survey_item) > 4000:
            chunks.append(current_chunk)
            chunk_count += 1
            current_chunk = f"Активные опросы (часть {chunk_count + 1}):\n\n{survey_item}"
        else:
            current_chunk += survey_item

    # Добавляем последний чанк
    if current_chunk:
        chunks.append(current_chunk)

    # Отправляем первый чанк сразу
    if chunks:
        await update.message.reply_text(chunks[0])

        # Остальные чанки отправляем с задержкой
        for chunk in chunks[1:]:
            await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями
            await update.message.reply_text(chunk)

        # Добавляем итоговую информацию
        await update.message.reply_text(f"Всего активных опросов: {len(surveys)}")
    else:
        await update.message.reply_text(SURVEY_TEXTS['no_active_surveys_found'])

async def syncjira_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Синхронизация данных Jira - работает в фоне"""

    user_role = context.user_data.get('user_role')

    if not user_role:
        await update.message.reply_text(AUTH_TEXTS['not_authorized'])
        return

    role_category = get_role_category(user_role)

    if role_category != 'CEO':
        await update.message.reply_text(
            AUTH_TEXTS['no_permission'].format(
                role=user_role,
                required=get_category_display('CEO')
            )
        )
        return

    # Отправляем начальное сообщение
    message = await update.message.reply_text(
        "Запуск синхронизации данных Jira...\n\n"
        "Это может занять несколько минут.\n"
        "Вы можете продолжать использовать бота!",
    )

    # Получаем текущий event loop
    import asyncio
    loop = asyncio.get_event_loop()

    # Запускаем синхронизацию в отдельном потоке
    def sync_in_thread():
        try:
            from tg_bot.services.jira_loader import jira_loader

            # Синхронные операции в отдельном потоке
            jira_loader.clear_old_data()
            success = jira_loader.load_all_data()

            # Используем asyncio.run_coroutine_threadsafe для отправки результата
            async def send_result():
                if success:
                    await message.edit_text(
                        "Синхронизация завершена успешно!\n\n"
                        "Все данные Jira обновлены."
                    )
                else:
                    await message.edit_text(
                        "Синхронизация завершена с ошибками"
                    )

            # Отправляем задачу в основной event loop
            asyncio.run_coroutine_threadsafe(send_result(), loop)

        except Exception as e:
            logger.error(f"Ошибка синхронизации в потоке: {e}")

            # Отправляем сообщение об ошибке
            async def send_error():
                await message.edit_text(
                    f"Ошибка синхронизации:\n{str(e)[:200]}"
                )

            asyncio.run_coroutine_threadsafe(send_error(), loop)

    # Запускаем поток
    import threading
    thread = threading.Thread(target=sync_in_thread, daemon=True)
    thread.start()

    # Сохраняем информацию о запущенной синхронизации
    context.user_data['jira_sync_in_progress'] = True
    context.user_data['jira_sync_message'] = message
    context.user_data['jira_sync_thread'] = thread


def role_required(allowed_categories):
    """Декоратор для проверки категории роли пользователя"""

    def decorator(handler):
        async def wrapper(update, context):
            user_role = context.user_data.get('user_role')

            if not user_role:
                await update.message.reply_text(AUTH_TEXTS['not_authorized'])
                return

            from tg_bot.config.roles_config import get_role_category
            role_category = get_role_category(user_role)

            if not role_category:
                await update.message.reply_text(AUTH_TEXTS['unknown_role'])
                return

            if role_category not in allowed_categories:
                required_categories = [get_category_display(cat) for cat in allowed_categories]
                await update.message.reply_text(
                    AUTH_TEXTS['no_permission'].format(
                        role=user_role,
                        required=', '.join(required_categories)
                    )
                )
                return

            return await handler(update, context)

        return wrapper

    return decorator

def main():
    """Основная функция запуска бота"""
    application = Application.builder().token(config.BOT_TOKEN).build()
    logger.info("Запуск бота...")

    # Проверка подключения к БД
    logger.info("Проверка подключения к БД...")
    from tg_bot.database.connection import db_connection
    test_connection = db_connection.get_connection()
    if test_connection:
        logger.info("Подключение к БД успешно")
        test_connection.close()
    else:
        logger.error("Не удалось подключиться к БД")
        return

    if config.JIRA_URL and config.JIRA_SYNC_ON_START:
        logger.info("Запуск загрузки данных Jira при старте...")
        try:
            # Запускаем синхронизацию синхронно (это блокирующая операция)
            from tg_bot.services.jira_loader import load_jira_data_on_startup
            success = load_jira_data_on_startup(clear_old=config.JIRA_CLEAR_OLD_DATA)

            if success:
                logger.info("Данные Jira успешно загружены при старте")
            else:
                logger.warning("Загрузка данных Jira завершилась с ошибками")
                logger.warning("Бот продолжит работу без полных данных Jira")

        except Exception as e:
            logger.error(f"Критическая ошибка при загрузке Jira: {e}")
            logger.warning("Бот продолжит работу без данных Jira")
    else:
        if not config.JIRA_URL:
            logger.info("Jira URL не указан, пропускаем загрузку данных")
        elif not config.JIRA_SYNC_ON_START:
            logger.info("JIRA_SYNC_ON_START=false, пропускаем загрузку данных")
        else:
            logger.info("Загрузка данных Jira отключена")

    # Инициализируем планировщик и сохраняем в bot_data
    survey_scheduler = SurveyScheduler(application.bot)
    application.bot_data['survey_scheduler'] = survey_scheduler

    # Импортируем обработчики
    from tg_bot.handlers.survey_handlers import survey_response_conversation, survey_creation_conversation
    from tg_bot.handlers.report_handlers import dailydigest_command, weeklydigest_command, blockers_command

    # Создаем ConversationHandler для регистрации
    registration_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            AWAITING_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
            AWAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
            AWAITING_JIRA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
            AWAITING_ROLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_command)],
        per_user=True,
        per_chat=True
    )

    # РЕГИСТРИРУЕМ ОБРАБОТЧИКИ
    application.add_handler(registration_handler)
    application.add_handler(survey_creation_conversation)
    application.add_handler(survey_response_conversation)

    # Команды
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("mysurveys", mysurveys_command))
    application.add_handler(CommandHandler("syncjira", syncjira_command))

    @role_required(['CEO'])
    async def dailydigest_wrapper(update, context):
        return await dailydigest_command(update, context)

    @role_required(['CEO'])
    async def weeklydigest_wrapper(update, context):
        return await weeklydigest_command(update, context)

    @role_required(['CEO'])
    async def blockers_wrapper(update, context):
        return await blockers_command(update, context)

    @role_required(['worker', 'CEO'])
    async def response_command_wrapper(update, context):
        from tg_bot.handlers.survey_handlers import response_command
        return await response_command(update, context)

    application.add_handler(CommandHandler("dailydigest", dailydigest_wrapper))
    application.add_handler(CommandHandler("weeklydigest", weeklydigest_wrapper))
    application.add_handler(CommandHandler("blockers", blockers_wrapper))
    application.add_handler(CommandHandler("response", response_command_wrapper))

    # Общий обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем планировщик при старте бота
    async def startup():
        await survey_scheduler.start()
        logger.info("Планировщик опросов запущен")

    # Исправленная строка - используем asyncio.new_event_loop() вместо get_event_loop()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(startup())

    # Запускаем бота
    logger.info("Бот готов к работе")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()