import logging
import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, \
    CallbackQueryHandler

from tg_bot.config.roles_config import get_role_category
from tg_bot.config.settings import config
from tg_bot.config.constants import (
    AWAITING_PASSWORD,
    AWAITING_NAME,
    AWAITING_JIRA,
    AWAITING_ROLE, ALLSURVEYS_PAGINATION_PREFIX, ALLSURVEYS_PERIOD_DAYS
)
from tg_bot.handlers.addresponse_handlers import addresponse_conversation
from tg_bot.handlers.auth_handlers import start_command, handle_message
from tg_bot.handlers.menu_handlers import setup_bot_commands, setup_menu_handlers
from tg_bot.handlers.pagination_handlers import setup_pagination_handlers
from tg_bot.handlers.report_handlers import report_command, setup_report_handlers
from tg_bot.handlers.role_handlers import handle_subtype_selection, handle_category_selection
from tg_bot.handlers.scheduler import SurveyScheduler

from tg_bot.config.texts import (
    HELP_TEXTS, format_profile, get_category_display, GENERAL_TEXTS, AUTH_TEXTS,
)
from tg_bot.handlers.survey_handlers import finish_response_command
from tg_bot.services.pagination_utils import PaginationUtils

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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help с учетом категории ролей"""
    user_role = context.user_data.get('user_role')

    if not user_role:
        response_text = AUTH_TEXTS['not_authorized']
    else:
        from tg_bot.config.roles_config import get_role_category
        role_category = get_role_category(user_role)

        if not role_category:
            response_text = AUTH_TEXTS['unknown_role']
        else:
            if role_category == 'CEO':
                response_text = HELP_TEXTS['ceo']
            elif role_category == 'worker':
                response_text = HELP_TEXTS['worker']
            else:
                response_text = HELP_TEXTS['unknown_category']

    # Проверяем, вызвана ли команда из меню
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(response_text)
    else:
        await update.message.reply_text(response_text)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя"""
    user_role = context.user_data.get('user_role')
    user_name = context.user_data.get('user_name')
    jira_account = context.user_data.get('jira_account')

    if not user_role:
        response_text = AUTH_TEXTS['not_authorized']
    else:
        chat_id = update.effective_user.id
        response_text = format_profile(
            name=user_name,
            role=user_role,
            jira_account=jira_account,
            chat_id=chat_id
        )

    # Проверяем, вызвана ли команда из меню (через callback_query)
    if hasattr(update, 'callback_query') and update.callback_query:
        # Редактируем существующее сообщение
        await update.callback_query.edit_message_text(response_text)
    else:
        # Отправляем новое сообщение
        await update.message.reply_text(response_text)


async def allsurveys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать созданные опросы с пагинацией"""
    from tg_bot.config.roles_config import get_role_category
    from tg_bot.database.models import SurveyModel

    user_role = context.user_data.get('user_role')
    role_category = get_role_category(user_role) if user_role else None

    if role_category != 'CEO':
        response_text = GENERAL_TEXTS['survey_view_permission']
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return

    # Вычисляем дату N дней назад из настроек
    from datetime import datetime, timedelta
    period_days = ALLSURVEYS_PERIOD_DAYS
    date_from = datetime.now() - timedelta(days=period_days)

    # Получаем опросы с ограничением по дате
    surveys = SurveyModel.get_active_surveys_since(date_from)

    if not surveys:
        response_text = f"Нет активных опросов за последние {period_days} дней."
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return

    # Сохраняем опросы для пагинации
    context.user_data['pagination_allsurveys'] = {
        'items': surveys,
        'type': 'allsurveys'
    }

    # Всегда показываем пагинацию
    if hasattr(update, 'callback_query') and update.callback_query:
        # Через меню
        await _show_allsurveys_page(query=update.callback_query, context=context, page=0)
    else:
        # Через текстовую команду
        await _send_allsurveys_page(message_obj=update.message, context=context, page=0)


async def _show_allsurveys_page(query, context, page=0):
    """Показать страницу с пагинацией всех опросов (для меню)"""
    user_data = context.user_data
    items = user_data.get('pagination_allsurveys', {}).get('items', [])

    if not items:
        await query.edit_message_text("Нет активных опросов.")
        return

    page_items, current_page, total_pages = PaginationUtils.get_page_items(items, page)

    # Форматируем сообщение с указанием периода
    from tg_bot.config.constants import ALLSURVEYS_PERIOD_DAYS
    title = f"ВСЕ АКТИВНЫЕ ОПРОСЫ ({ALLSURVEYS_PERIOD_DAYS} дней)"

    message = PaginationUtils.format_page_with_numbers(
        page_items, current_page, total_pages, title
    )

    # Создаем клавиатуру навигации
    keyboard = PaginationUtils.create_pagination_navigation(
        page=current_page,
        total_pages=total_pages,
        callback_prefix=ALLSURVEYS_PAGINATION_PREFIX
    )

    await query.edit_message_text(
        message,
        reply_markup=keyboard
    )


async def _send_allsurveys_page(message_obj, context, page=0):
    """Отправить страницу всех опросов (для текстовой команды)"""
    user_data = context.user_data
    items = user_data.get('pagination_allsurveys', {}).get('items', [])

    if not items:
        from tg_bot.config.constants import ALLSURVEYS_PERIOD_DAYS
        await message_obj.reply_text(f"Нет активных опросов за последние {ALLSURVEYS_PERIOD_DAYS} дней.")
        return

    page_items, current_page, total_pages = PaginationUtils.get_page_items(items, page)

    # Форматируем сообщение с указанием периода
    from tg_bot.config.constants import ALLSURVEYS_PERIOD_DAYS
    title = f"ВСЕ АКТИВНЫЕ ОПРОСЫ ({ALLSURVEYS_PERIOD_DAYS} дней)"

    message = PaginationUtils.format_page_with_numbers(
        page_items, current_page, total_pages, title
    )

    # Создаем клавиатуру навигации
    keyboard = PaginationUtils.create_pagination_navigation(
        page=current_page,
        total_pages=total_pages,
        callback_prefix=ALLSURVEYS_PAGINATION_PREFIX
    )

    await message_obj.reply_text(
        message,
        reply_markup=keyboard
    )


async def syncjira_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Синхронизация данных Jira - работает в фоне"""
    user_role = context.user_data.get('user_role')

    if not user_role:
        response_text = AUTH_TEXTS['not_authorized']
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return

    role_category = get_role_category(user_role)

    if role_category != 'CEO':
        response_text = AUTH_TEXTS['no_permission'].format(
            role=user_role,
            required=get_category_display('CEO')
        )
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return

    # Проверяем, вызвана ли команда из меню
    menu_message = None
    if hasattr(update, 'callback_query') and update.callback_query:
        # В режиме меню показываем упрощенное сообщение
        response_text = (
            "Запуск синхронизации данных Jira...\n\n"
            "Это может занять несколько минут.\n"
            "Результат будет отправлен отдельным сообщением."
        )
        await update.callback_query.edit_message_text(response_text)
        # Сохраняем информацию о сообщении меню
        menu_message = update.callback_query.message
    else:
        response_text = (
            "Запуск синхронизации данных Jira...\n\n"
            "Это может занять несколько минут.\n"
            "Вы можете продолжать использовать бота!"
        )
        message_obj = await update.message.reply_text(response_text)
        menu_message = message_obj  # Переименовываем для единообразия

    # Далее оригинальная логика синхронизации...
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
                    result_text = "Синхронизация завершена успешно!\n\nВсе данные Jira обновлены."
                else:
                    result_text = "Синхронизация завершена с ошибками"

                # Отправляем результат в то же сообщение меню
                if menu_message:
                    # Используем правильный метод в зависимости от типа вызова
                    if hasattr(update, 'callback_query') and update.callback_query:
                        await update.callback_query.edit_message_text(result_text)
                    else:
                        # Для обычного сообщения обновляем текст
                        await menu_message.edit_text(result_text)

            asyncio.run_coroutine_threadsafe(send_result(), loop)

        except Exception as e:
            logger.error(f"Ошибка синхронизации в потоке: {e}")

            async def send_error():
                error_text = f"Ошибка синхронизации:\n{str(e)[:200]}"
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text(error_text)
                else:
                    # Для обычного сообщения обновляем текст
                    await menu_message.edit_text(error_text)

            asyncio.run_coroutine_threadsafe(send_error(), loop)

    # Запускаем поток
    import threading
    thread = threading.Thread(target=sync_in_thread, daemon=True)
    thread.start()

    # Сохраняем информацию о запущенной синхронизации
    context.user_data['jira_sync_in_progress'] = True
    context.user_data['jira_sync_message'] = menu_message
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
    # Создаем application с явным удалением webhook
    application = Application.builder().token(config.BOT_TOKEN).build()
    logger.info("Запуск бота...")

    setup_bot_commands(application)

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

    # Настраиваем команды бота для меню
    application.add_handler(CommandHandler("setupcommands", lambda update, context: setup_bot_commands(application)))

    # Импортируем обработчики
    from tg_bot.handlers.survey_handlers import survey_response_conversation, survey_creation_conversation
    from tg_bot.handlers.role_handlers import setup_role_handlers
    from tg_bot.handlers.survey_target_handlers import setup_survey_target_handlers
    from tg_bot.handlers.report_handlers import setup_report_handlers, report_command  # ДОБАВЛЕНО

    # Создаем ConversationHandler для регистрации
    from tg_bot.config.constants import AWAITING_SUBROLE
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
                CallbackQueryHandler(handle_category_selection, pattern=f"^cat_")
            ],
            AWAITING_SUBROLE: [
                CallbackQueryHandler(handle_subtype_selection, pattern=f"^sub_")
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_command)],
        per_user=True,
        per_chat=True
    )

    setup_pagination_handlers(application)

    # Настраиваем обработчики выбора ролей
    setup_role_handlers(application)

    # Настраиваем обработчики выбора получателей опроса
    setup_survey_target_handlers(application)

    # Настраиваем обработчики отчетов
    setup_report_handlers(application)  # ДОБАВЛЕНО

    # РЕГИСТРИРУЕМ ОБРАБОТЧИКИ (порядок важен!)
    application.add_handler(registration_handler)
    application.add_handler(survey_creation_conversation)
    application.add_handler(survey_response_conversation)
    application.add_handler(addresponse_conversation)

    # Настраиваем обработчики меню
    setup_menu_handlers(application)

    # Команды
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("allsurveys", allsurveys_command))
    application.add_handler(CommandHandler("syncjira", syncjira_command))

    # Обертки для команд с проверкой ролей
    @role_required(['worker', 'CEO'])
    async def response_command_wrapper(update, context):
        from tg_bot.handlers.survey_handlers import response_command
        return await response_command(update, context)

    @role_required(['worker', 'CEO'])
    async def addresponse_command_wrapper(update, context):
        from tg_bot.handlers.addresponse_handlers import addresponse_command
        return await addresponse_command(update, context)

    application.add_handler(CommandHandler("response", response_command_wrapper))
    application.add_handler(CommandHandler("addresponse", addresponse_command_wrapper))
    application.add_handler(CommandHandler("done", finish_response_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных команд"""
        command = update.message.text.split()[0] if update.message.text else ""

        if command in ['/dailydigest', '/weeklydigest', '/blockers']:
            return await report_command(update, context)

        await update.message.reply_text(
            "Неизвестная команда. Используйте /help для списка доступных команд."
        )

    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Запускаем бота с более агрессивными параметрами для очистки webhook
    logger.info("Бот готов к работе")

    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        close_loop=False
    )


if __name__ == '__main__':
    main()
