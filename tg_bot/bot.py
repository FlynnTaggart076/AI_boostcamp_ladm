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

from tg_bot.services.jira_loader import sync_jira_data_with_progress

from tg_bot.config.texts import (
    HELP_TEXTS, PROFILE_TEXTS, JIRA_TEXTS, AUTH_TEXTS,
    get_role_display_name, format_profile, get_category_display
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
        "Регистрация отменена. Используйте /start для повторной попытки."
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
            "Только руководители могут просматривать опросы."
        )
        return

    from tg_bot.database.models import SurveyModel
    surveys = SurveyModel.get_active_surveys()

    if not surveys:
        await update.message.reply_text(
            "Нет активных опросов."
        )
        return

    response = "Активные опросы:\n\n"
    for survey in surveys:
        role_display = survey['role'] if survey['role'] else 'все'
        response += (
            f"ID: {survey['id_survey']}\n"
            f"Вопрос: {survey['question'][:50]}...\n"
            f"Для: {role_display}\n"
            f"Время: {survey['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
            f"Статус: {survey['state']}\n\n"
        )

    await update.message.reply_text(response)


async def syncjira_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Синхронизация данных Jira - только для руководителей"""

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

    # Уведомляем пользователя о начале синхронизации
    await update.message.reply_text(
        "🔄 *Запуск синхронизации данных Jira*\n\n"
        "Этапы синхронизации:\n"
        "1. 🧹 Очистка старых данных\n"
        "2. 👥 Загрузка пользователей\n"
        "3. 📁 Загрузка проектов\n"
        "4. 📋 Загрузка досок\n"
        "5. 🏃 Загрузка спринтов\n"
        "6. 📝 Загрузка задач\n\n"
        "⏳ *Это может занять несколько минут...*",
        parse_mode='Markdown'
    )

    try:
        # Запускаем синхронизацию с передачей update и context для прогресса
        import threading

        # Запускаем в отдельном потоке, чтобы не блокировать бота
        def sync_thread():
            success = sync_jira_data_with_progress(update, context)
            return success

        # Создаем и запускаем поток
        sync_thread_obj = threading.Thread(target=sync_thread)
        sync_thread_obj.start()

        # Сообщаем, что синхронизация запущена в фоне
        await update.message.reply_text(
            "🔧 *Синхронизация запущена в фоновом режиме*\n"
            "Вы получите уведомление по завершении каждого этапа.",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Ошибка запуска синхронизации Jira: {e}")
        await update.message.reply_text(
            "❌ *Не удалось запустить синхронизацию*\n"
            "Проверьте подключение к Jira или обратитесь к администратору.",
            parse_mode='Markdown'
        )


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
        logger.info("✅ Подключение к БД успешно")
        test_connection.close()
    else:
        logger.error("❌ Не удалось подключиться к БД")
        return

    # НОВЫЙ БЛОК: Загрузка данных Jira при старте (если включено)
    if config.JIRA_URL and config.JIRA_SYNC_ON_START:
        logger.info("🔄 Запуск загрузки данных Jira при старте...")
        try:
            # Запускаем синхронизацию синхронно (это блокирующая операция)
            from tg_bot.services.jira_loader import load_jira_data_on_startup
            success = load_jira_data_on_startup(clear_old=config.JIRA_CLEAR_OLD_DATA)

            if success:
                logger.info("✅ Данные Jira успешно загружены при старте")
            else:
                logger.warning("⚠️ Загрузка данных Jira завершилась с ошибками")
                logger.warning("Бот продолжит работу без полных данных Jira")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка при загрузке Jira: {e}")
            logger.warning("Бот продолжит работу без данных Jira")
    else:
        if not config.JIRA_URL:
            logger.info("⚠️ Jira URL не указан, пропускаем загрузку данных")
        elif not config.JIRA_SYNC_ON_START:
            logger.info("⚠️ JIRA_SYNC_ON_START=false, пропускаем загрузку данных")
        else:
            logger.info("⚠️ Загрузка данных Jira отключена")

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
        logger.info("✅ Планировщик опросов запущен")

    # Исправленная строка - используем asyncio.new_event_loop() вместо get_event_loop()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(startup())

    # Запускаем бота
    logger.info("✅ Бот готов к работе")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()