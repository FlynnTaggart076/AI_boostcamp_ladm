# -*- coding: utf-8 -*-
import logging

import telegram
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from tg_bot.config.roles_config import get_role_category
from tg_bot.config.texts import AUTH_TEXTS

logger = logging.getLogger(__name__)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /menu - показывает интерактивное меню"""
    user_role = context.user_data.get('user_role')

    if not user_role:
        await update.message.reply_text(AUTH_TEXTS['not_authorized'])
        return

    role_category = get_role_category(user_role)


    if role_category == 'CEO':
        # Кнопки для руководителей (дополнительно к общим)
        keyboard = [
            [
                InlineKeyboardButton("📊 Отчеты", callback_data="menu_reports"),
                InlineKeyboardButton("📝 Опросы", callback_data="menu_surveys")
            ],
            [
                InlineKeyboardButton("📝 Ответить на опрос", callback_data="menu_response"),
                InlineKeyboardButton("➕ Дополнить ответ", callback_data="menu_addresponse")
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
    else:
        # Кнопки для всех остальных пользователей (worker и другие)
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

    # Проверяем, авторизован ли пользователь
    if not user_role:
        await query.edit_message_text("Сначала авторизуйтесь с помощью /start")
        return

    simple_commands = {
        'menu_response': ('ответа на опрос', 'response'),
        'menu_addresponse': ('дополнения старого ответа', 'addresponse'),
        'survey_create': ('создания опроса', 'sendsurvey')
    }

    if callback_data in simple_commands:
        action_name, command = simple_commands[callback_data]
        # Вместо редиректа на команду, вызываем обработчик напрямую
        if command == 'response':
            from tg_bot.handlers.survey_handlers import response_command
            return await response_command(update, context)
        elif command == 'addresponse':
            from tg_bot.handlers.addresponse_handlers import addresponse_command
            return await addresponse_command(update, context)
        elif command == 'sendsurvey':
            from tg_bot.handlers.survey_handlers import sendsurvey_command
            return await sendsurvey_command(update, context)

    # Маппинг callback_data на команды для остальных кнопок
    command_map = {
        'menu_profile': ('profile', []),
        'menu_help': ('help', []),
        'menu_sync': ('syncjira', []),
        'report_daily': ('dailydigest', []),
        'report_weekly': ('weeklydigest', []),
        'report_blockers': ('blockers', []),
        'survey_list': ('allsurveys', []),
    }

    if callback_data == "menu_close":
        await query.edit_message_text("Меню закрыто. Используйте /menu для повторного открытия.")
        return

    elif callback_data == "menu_reports":
        # Отчеты доступны только руководителям
        if role_category == 'CEO':
            await show_reports_menu(query)
        else:
            await query.edit_message_text("У вас нет доступа к отчетам.")
        return

    elif callback_data == "menu_surveys":
        # Управление опросами доступно только руководителям
        if role_category == 'CEO':
            await show_surveys_menu(query)
        else:
            await query.edit_message_text("У вас нет доступа к управлению опросами.")
        return

    elif callback_data == "menu_back":
        await show_main_menu(query, role_category)
        return

    ceo_only_commands = ['syncjira', 'dailydigest', 'weeklydigest', 'blockers', 'sendsurvey', 'allsurveys']

    if callback_data in command_map:
        command_name, args = command_map[callback_data]

        # Проверка доступа для CEO-only команд
        if command_name in ceo_only_commands and role_category != 'CEO':
            await query.edit_message_text(f"У вас нет доступа к команде {command_name}")
            return

        await handle_menu_command(update, context, command_name, args)
    else:
        # Если callback_data не из меню, просто игнорируем - его обработают другие обработчики
        # НЕ делаем await query.edit_message_text() чтобы не мешать другим обработчикам
        return


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


async def show_main_menu(query, role_category):
    """Показать главное меню"""
    if role_category == 'CEO':
        keyboard = [
            [
                InlineKeyboardButton("📊 Отчеты", callback_data="menu_reports"),
                InlineKeyboardButton("📝 Опросы", callback_data="menu_surveys")
            ],
            [
                InlineKeyboardButton("📝 Ответить на опрос", callback_data="menu_response"),
                InlineKeyboardButton("➕ Дополнить ответ", callback_data="menu_addresponse")
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
    else:
        # Для всех остальных пользователей
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
        "📊 **Меню отчеты**\n\n"
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


def setup_menu_handlers(application):
    """Настроить обработчики меню"""
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^report_"))
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^survey_"))
