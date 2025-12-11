import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from config.settings import config
from config.constants import (
    AWAITING_PASSWORD,
    AWAITING_NAME,
    AWAITING_JIRA,
    AWAITING_ROLE
)
from handlers.auth_handlers import start_command, handle_message
from handlers.scheduler import SurveyScheduler
from services.jira_handler import process_jira_registration

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



async def cancel_command(update, context):
    """Отмена регистрации"""
    # Очищаем все данные регистрации
    for key in ['awaiting_password', 'awaiting_name', 'awaiting_jira',
                'awaiting_role', 'user_name', 'jira_account']:
        context.user_data.pop(key, None)

    await update.message.reply_text(
        "Регистрация отменена. Используйте /start для повторной попытки."
    )

    return ConversationHandler.END


async def help_command(update, context):
    """Обработчик команды /help с учетом роли"""
    user_role = context.user_data.get('user_role')

    if not user_role:
        await update.message.reply_text(
            "Сначала авторизуйтесь с помощью /start"
        )
        return

    # Разные справки для разных ролей
    if user_role == 'CEO':
        help_text = """
Руководитель (CEO) - доступные команды:

Просмотр отчетов:
/dailydigest [дата] - ежедневный дайджест
/weeklydigest [начало] [конец] - еженедельный дайджест  
/blockers [дата] - список блокеров

Управление опросами:
/sendsurvey - создать и отправить опрос
/mysurveys - просмотреть созданные опросы

Ответы на опросы (для отладки):
/response - ответить на опрос
"""
    elif user_role == 'worker':
        help_text = """
Рабочий - доступные команды:

Ответы на опросы:
/response - ответить на опрос от руководителя
"""
    else:
        help_text = "Неизвестная роль. Обратитесь к администратору."

    await update.message.reply_text(help_text)


async def profile_command(update, context):
    """Показать профиль пользователя"""
    user_role = context.user_data.get('user_role')
    user_name = context.user_data.get('user_name')
    jira_account = context.user_data.get('jira_account')

    if not user_role:
        await update.message.reply_text(
            "Сначала авторизуйтесь с помощью /start"
        )
        return

    role_display = {
        'worker': 'Рабочий',
        'CEO': 'Руководитель'
    }.get(user_role, user_role)

    jira_info = f"Jira: {jira_account}" if jira_account else "📋 Jira: не указан"

    chat_id = update.effective_user.id

    await update.message.reply_text(
        f"Ваш профиль:\n\n"
        f"Имя: {user_name}\n"
        f"Роль: {role_display}\n"
        f"{jira_info}\n"
        f"Telegram Chat ID: {chat_id}"
    )


async def mysurveys_command(update, context):
    """Показать созданные опросы"""
    user_role = context.user_data.get('user_role')

    if not user_role:
        await update.message.reply_text(
            "Сначала авторизуйтесь с помощью /start"
        )
        return

    # Пока только для CEO
    if user_role != 'CEO':
        await update.message.reply_text(
            "Только руководители могут просматривать опросы."
        )
        return

    # Получаем все активные опросы
    from database.models import SurveyModel
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


async def syncjira_command(update, context):
    """Синхронизация данных Jira"""
    user_role = context.user_data.get('user_role')
    user_id = context.user_data.get('user_id')
    jira_account = context.user_data.get('jira_account')
    user_name = context.user_data.get('user_name')

    if not user_role:
        await update.message.reply_text("Сначала авторизуйтесь с помощью /start")
        return

    if not jira_account:
        await update.message.reply_text(
            "У вас не указан Jira аккаунт.\n"
            "Используйте команду /profile для просмотра профиля."
        )
        return

    await update.message.reply_text(
        f"🔄 Начинаю синхронизацию с Jira для {jira_account}..."
    )

    try:

        success = await process_jira_registration(user_id, jira_account, user_name)

        if success:
            await update.message.reply_text(
                "✅ Синхронизация с Jira завершена успешно!\n"
                "Все проекты, задачи и спринты обновлены."
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось синхронизировать с Jira.\n"
                "Проверьте правильность Jira аккаунта или обратитесь к администратору."
            )
    except Exception as e:
        logger.error(f"Ошибка синхронизации Jira: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при синхронизации.\n"
            "Попробуйте позже или обратитесь к администратору."
        )

def role_required(allowed_roles):
    """Декоратор для проверки роли пользователя"""

    def decorator(handler):
        async def wrapper(update, context):
            user_role = context.user_data.get('user_role')

            if not user_role:
                await update.message.reply_text(
                    "Требуется авторизация. Используйте /start"
                )
                return

            if user_role not in allowed_roles:
                await update.message.reply_text(
                    f"У вас нет прав для выполнения этой команды.\n"
                    f"Ваша роль: {user_role}\n"
                    f"Требуемые роли: {', '.join(allowed_roles)}"
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
    from database.connection import db_connection
    test_connection = db_connection.get_connection()
    if test_connection:
        logger.info("✅ Подключение к БД успешно")
        test_connection.close()
    else:
        logger.error("❌ Не удалось подключиться к БД")
        return

    # Инициализируем планировщик и сохраняем в bot_data
    survey_scheduler = SurveyScheduler(application.bot)
    application.bot_data['survey_scheduler'] = survey_scheduler

    # Импортируем обработчики
    from handlers.survey_handlers import survey_response_conversation, survey_creation_conversation
    from handlers.report_handlers import dailydigest_command, weeklydigest_command, blockers_command

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

    # РЕГИСТРИРУЕМ ОБРАБОТЧИКИ В ПРАВИЛЬНОМ ПОРЯДКЕ
    # 1. Сначала ConversationHandler'ы (они более специфичные)
    application.add_handler(registration_handler)
    application.add_handler(survey_creation_conversation)  # Для создания опросов
    application.add_handler(survey_response_conversation)  # Для ответов на опросы

    # 2. Затем обычные CommandHandler'ы
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("mysurveys", mysurveys_command))
    application.add_handler(CommandHandler("syncjira", syncjira_command))


    # Оборачиваем команды отчетов в декораторы проверки ролей
    @role_required(['CEO'])
    async def dailydigest_wrapper(update, context):
        return await dailydigest_command(update, context)

    @role_required(['CEO'])
    async def weeklydigest_wrapper(update, context):
        return await weeklydigest_command(update, context)

    @role_required(['CEO'])
    async def blockers_wrapper(update, context):
        return await blockers_command(update, context)

    # Оборачиваем команду ответа на опрос (response_command уже внутри survey_response_conversation)
    # Поэтому просто добавляем CommandHandler для /response (если нужно)
    @role_required(['worker', 'CEO'])
    async def response_command_wrapper(update, context):
        from handlers.survey_handlers import response_command
        return await response_command(update, context)

    application.add_handler(CommandHandler("dailydigest", dailydigest_wrapper))
    application.add_handler(CommandHandler("weeklydigest", weeklydigest_wrapper))
    application.add_handler(CommandHandler("blockers", blockers_wrapper))
    # Команда /response уже обрабатывается survey_response_conversation, но добавляем на всякий случай
    application.add_handler(CommandHandler("response", response_command_wrapper))

    # 3. В самом конце общий обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем планировщик при старте бота
    async def startup():
        await survey_scheduler.start()
        logger.info("✅ Планировщик опросов запущен")

    # Создаем и запускаем задачу для планировщика
    loop = asyncio.get_event_loop()
    task = loop.create_task(startup())

    # Запускаем бота
    application.run_polling(drop_pending_updates=True)



if __name__ == '__main__':
    main()
