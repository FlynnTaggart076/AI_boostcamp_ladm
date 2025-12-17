# -*- coding: utf-8 -*-
import logging

import telegram
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    MenuButtonCommands,
    MenuButton
)
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from tg_bot.config.texts import HELP_TEXTS, AUTH_TEXTS
from tg_bot.config.roles_config import get_role_category

logger = logging.getLogger(__name__)


async def set_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить кнопку меню с командами"""
    try:
        # Устанавливаем меню-кнопку с командами
        await context.bot.set_chat_menu_button(
            chat_id=update.effective_chat.id,
            menu_button=MenuButtonCommands()
        )
        logger.info(f"Меню-кнопка установлена для чата {update.effective_chat.id}")
    except Exception as e:
        logger.error(f"Ошибка установки меню-кнопки: {e}")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /menu - показывает интерактивное меню"""
    user_role = context.user_data.get('user_role')

    if not user_role:
        await update.message.reply_text(AUTH_TEXTS['not_authorized'])
        return

    role_category = get_role_category(user_role)

    # Создаем клавиатуру в зависимости от категории роли
    keyboard = []

    if role_category == 'CEO':
        # Кнопки для руководителей
        keyboard = [
            [
                InlineKeyboardButton("📊 Отчеты", callback_data="menu_reports"),
                InlineKeyboardButton("📝 Опросы", callback_data="menu_surveys")
            ],
            [
                InlineKeyboardButton("🔄 Синхронизация", callback_data="menu_sync"),
                InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")
            ],
            [
                InlineKeyboardButton("❓ Помощь", callback_data="menu_help"),
                InlineKeyboardButton("✖️ Закрыть", callback_data="menu_close")
            ]
        ]
    elif role_category == 'worker':
        # Кнопки для работников
        keyboard = [
            [
                InlineKeyboardButton("📝 Ответить на опрос", callback_data="menu_response"),
                InlineKeyboardButton("➕ Дополнить ответ", callback_data="menu_addresponse")
            ],
            [
                InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
                InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
            ],
            [
                InlineKeyboardButton("✖️ Закрыть", callback_data="menu_close")
            ]
        ]
    else:
        await update.message.reply_text(AUTH_TEXTS['unknown_role'])
        return

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📱 **Главное меню**\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок меню"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    user_role = context.user_data.get('user_role')
    role_category = get_role_category(user_role) if user_role else None

    # Маппинг callback_data на команды
    command_map = {
        'menu_profile': ('profile', []),
        'menu_help': ('help', []),
        'menu_sync': ('syncjira', []),
        'menu_response': ('response', []),
        'menu_addresponse': ('addresponse', []),
        'report_daily': ('dailydigest', []),
        'report_weekly': ('weeklydigest', []),
        'report_blockers': ('blockers', []),
        'survey_create': ('sendsurvey', []),
        'survey_list': ('allsurveys', []),
    }

    if callback_data == "menu_close":
        await query.edit_message_text("Меню закрыто. Используйте /menu для повторного открытия.")
        return

    elif callback_data == "menu_reports":
        if role_category == 'CEO':
            await show_reports_menu(query)
        else:
            await query.edit_message_text("У вас нет доступа к отчетам.")
        return

    elif callback_data == "menu_surveys":
        if role_category == 'CEO':
            await show_surveys_menu(query)
        else:
            await query.edit_message_text("У вас нет доступа к управлению опросами.")
        return

    elif callback_data == "menu_back":
        await show_main_menu(query, role_category)
        return

    # Проверка прав доступа для CEO команд
    ceo_commands = ['syncjira', 'dailydigest', 'weeklydigest', 'blockers', 'sendsurvey', 'allsurveys']

    if callback_data in command_map:
        command_name, args = command_map[callback_data]

        # Проверка доступа для CEO команд
        if command_name in ceo_commands and role_category != 'CEO':
            await query.edit_message_text(f"У вас нет доступа к команде {command_name}")
            return

        # Выполняем команду
        await handle_menu_command(update, context, command_name, args)
    else:
        await query.edit_message_text(f"Неизвестная команда меню: {callback_data}")


async def handle_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              command_name: str, args: list = None):
    """Универсальный обработчик команд из меню"""
    query = update.callback_query

    # Маппинг команд на функции
    command_handlers = {
        'profile': 'tg_bot.bot.profile_command',
        'help': 'tg_bot.bot.help_command',
        'allsurveys': 'tg_bot.bot.allsurveys_command',
        'syncjira': 'tg_bot.bot.syncjira_command',
        'response': 'tg_bot.handlers.survey_handlers.response_command',
        'addresponse': 'tg_bot.handlers.addresponse_handlers.addresponse_command',
        'dailydigest': 'tg_bot.handlers.report_handlers.dailydigest_command',
        'weeklydigest': 'tg_bot.handlers.report_handlers.weeklydigest_command',
        'blockers': 'tg_bot.handlers.report_handlers.blockers_command',
        'sendsurvey': 'tg_bot.handlers.survey_handlers.sendsurvey_command',
    }

    if command_name not in command_handlers:
        await query.edit_message_text(f"Команда {command_name} не поддерживается в меню")
        return

    # Импортируем обработчик
    module_name, func_name = command_handlers[command_name].rsplit('.', 1)
    module = __import__(module_name, fromlist=[func_name])
    handler_func = getattr(module, func_name)

    # Устанавливаем аргументы
    if args is not None:
        context.args = args

    # Вызываем обработчик
    try:
        await handler_func(update, context)
    except Exception as e:
        logger.error(f"Ошибка выполнения команды {command_name} из меню: {e}")
        await query.edit_message_text(f"Ошибка выполнения команды: {str(e)[:100]}...")

def create_message_from_callback(query):
    """Создает объект Message из CallbackQuery для обработчиков команд"""
    from telegram import Message
    from datetime import datetime

    # Создаем fake message
    fake_message = Message(
        message_id=query.message.message_id,
        date=query.message.date or datetime.now(),
        chat=query.message.chat,
        text=""  # Будет установлено в зависимости от команды
    )
    fake_message.from_user = query.from_user
    return fake_message


async def execute_command_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    command_name: str, handler_func, args: list = None):
    """Выполнить команду из меню"""
    query = update.callback_query

    # Создаем искусственное сообщение
    fake_message = create_message_from_callback(query)
    fake_message.text = f"/{command_name} {' '.join(args) if args else ''}"

    # Сохраняем оригинальные данные
    original_message = update.message
    original_text = update.message.text if update.message else None

    # Подменяем данные в update
    update.message = fake_message

    # Устанавливаем аргументы если нужно
    if args:
        context.args = args

    try:
        # Вызываем обработчик
        await handler_func(update, context)
    except Exception as e:
        logger.error(f"Ошибка выполнения команды {command_name} из меню: {e}")
        await query.edit_message_text(f"Ошибка выполнения команды: {str(e)[:100]}...")
    finally:
        # Восстанавливаем оригинальные данные
        update.message = original_message
        if original_text and update.message:
            update.message.text = original_text

async def show_main_menu(query, role_category):
    """Показать главное меню"""
    if role_category == 'CEO':
        keyboard = [
            [
                InlineKeyboardButton("📊 Отчеты", callback_data="menu_reports"),
                InlineKeyboardButton("📝 Опросы", callback_data="menu_surveys")
            ],
            [
                InlineKeyboardButton("🔄 Синхронизация", callback_data="menu_sync"),
                InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")
            ],
            [
                InlineKeyboardButton("❓ Помощь", callback_data="menu_help"),
                InlineKeyboardButton("✖️ Закрыть", callback_data="menu_close")
            ]
        ]
    elif role_category == 'worker':
        keyboard = [
            [
                InlineKeyboardButton("📝 Ответить на опрос", callback_data="menu_response"),
                InlineKeyboardButton("➕ Дополнить ответ", callback_data="menu_addresponse")
            ],
            [
                InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
                InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
            ],
            [
                InlineKeyboardButton("✖️ Закрыть", callback_data="menu_close")
            ]
        ]
    else:
        return

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📱 **Главное меню**\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_reports_menu(query):
    """Показать меню отчетов"""
    keyboard = [
        [
            InlineKeyboardButton("📅 Ежедневный дайджест", callback_data="report_daily"),
            InlineKeyboardButton("📊 Еженедельный дайджест", callback_data="report_weekly")
        ],
        [
            InlineKeyboardButton("🚫 Список блокеров", callback_data="report_blockers")
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="menu_back")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📊 **Меню отчетов**\n\n"
        "Выберите тип отчета:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_surveys_menu(query):
    """Показать меню опросов"""
    keyboard = [
        [
            InlineKeyboardButton("➕ Создать опрос", callback_data="survey_create"),
            InlineKeyboardButton("📋 Просмотреть опросы", callback_data="survey_list")
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="menu_back")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📝 **Меню опросов**\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def setup_bot_commands(application):
    """Настроить команды бота для меню"""
    # Базовые команды для ВСЕХ
    base_commands = [
        ("start", "Начать работу с ботом"),
        ("menu", "Открыть меню команд"),
        ("help", "Показать справку"),
        ("profile", "Показать профиль"),
        ("cancel", "Отменить текущую операцию"),
    ]

    try:
        await application.bot.set_my_commands(base_commands)
        logger.info("Базовые команды бота успешно настроены")
    except Exception as e:
        logger.error(f"Ошибка настройки команд бота: {e}")


async def update_user_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновить команды для конкретного пользователя в зависимости от его роли"""
    user_role = context.user_data.get('user_role')

    if not user_role:
        # Если пользователь не авторизован, показываем только базовые команды
        commands = [
            ("start", "Начать работу с ботом"),
            ("help", "Показать справку"),
            ("cancel", "Отменить текущую операцию"),
        ]
    else:
        from tg_bot.config.roles_config import get_role_category
        role_category = get_role_category(user_role)

        # Базовые команды для авторизованных
        commands = [
            ("start", "Начать работу с ботом"),
            ("menu", "Открыть меню команд"),
            ("help", "Показать справку"),
            ("profile", "Показать профиль"),
            ("cancel", "Отменить текущую операцию"),
            ("response", "Ответить на опрос"),
            ("addresponse", "Дополнить ответ на опрос"),
            ("done", "Завершить ответ на опрос"),
        ]

        if role_category == 'CEO':
            # Добавляем команды для руководителей
            ceo_commands = [
                ("sendsurvey", "Создать и отправить опрос"),
                ("allsurveys", "Просмотреть созданные опросы"),
                ("syncjira", "Синхронизировать данные с Jira"),
                ("dailydigest", "Ежедневный дайджест"),
                ("weeklydigest", "Еженедельный дайджест"),
                ("blockers", "Список блокеров"),
            ]
            commands.extend(ceo_commands)

    try:
        await context.bot.set_my_commands(
            commands,
            scope=telegram.BotCommandScopeChat(update.effective_chat.id)
        )
        logger.info(f"Команды обновлены для пользователя {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Ошибка обновления команд: {e}")


async def handle_menu_command_with_args(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                        command: str, handler_func, args: list = None):
    """Универсальная функция для выполнения команд из меню"""
    query = update.callback_query

    if args:
        context.args = args

    try:
        # Вызываем обработчик команды
        await handler_func(update, context)
    except Exception as e:
        logger.error(f"Ошибка выполнения команды {command}: {e}")
        await query.edit_message_text(f"Ошибка выполнения команды: {str(e)[:100]}...")

def setup_menu_handlers(application):
    """Настроить обработчики меню"""
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^report_"))
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^survey_"))

