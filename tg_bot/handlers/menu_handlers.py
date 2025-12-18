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
        # Кнопки для руководителей
        keyboard = [
            [
                InlineKeyboardButton("Отчеты", callback_data="menu_reports"),
                InlineKeyboardButton("Опросы", callback_data="menu_surveys")
            ],
            [
                InlineKeyboardButton("Ответить на опрос", callback_data="menu_response"),
                InlineKeyboardButton("Дополнить ответ", callback_data="menu_addresponse")
            ],
            [
                InlineKeyboardButton("Синхронизация", callback_data="menu_sync"),
                InlineKeyboardButton("Профиль", callback_data="menu_profile")
            ],
            [
                InlineKeyboardButton("Помощь", callback_data="menu_help"),
                InlineKeyboardButton("Закрыть", callback_data="menu_close")
            ]
        ]
    else:
        # Кнопки для всех остальных пользователей
        keyboard = [
            [
                InlineKeyboardButton("Ответить на опрос", callback_data="menu_response"),
                InlineKeyboardButton("Дополнить ответ", callback_data="menu_addresponse")
            ],
            [
                InlineKeyboardButton("Профиль", callback_data="menu_profile"),
                InlineKeyboardButton("Помощь", callback_data="menu_help")
            ],
            [
                InlineKeyboardButton("✖Закрыть", callback_data="menu_close")
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

    if not user_role:
        await query.edit_message_text("Сначала авторизуйтесь с помощью /start")
        return

    simple_commands = {
        'menu_response': ('Чтобы ответить на опрос, введите команду:', '/response'),
        'menu_addresponse': ('Чтобы дополнить старый ответ, введите команду:', '/addresponse'),
        'survey_create': ('Чтобы создать опрос, введите команду:', '/sendsurvey')
    }

    if callback_data in simple_commands:
        title, command = simple_commands[callback_data]
        await query.edit_message_text(f"{title}\n\n`{command}`", parse_mode='Markdown')
        return

    # Маппинг callback_data на команды
    command_map = {
        'menu_profile': ('profile', []),
        'menu_help': ('help', []),
        'menu_sync': ('syncjira', []),
        'menu_reports': ('report', []),
        'survey_list': ('allsurveys', []),
    }

    if callback_data == "menu_close":
        await query.edit_message_text("Меню закрыто. Используйте /menu для повторного открытия.")
        return

    elif callback_data == "menu_reports":
        # Обработка кнопки отчетов - вызываем report_command
        from tg_bot.handlers.report_handlers import report_command
        return await report_command(update, context)

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

    ceo_only_commands = ['syncjira', 'sendsurvey', 'allsurveys', 'report']

    if callback_data in command_map:
        command_name, args = command_map[callback_data]

        # Проверка доступа для CEO-only команд
        if command_name in ceo_only_commands and role_category != 'CEO':
            await query.edit_message_text(f"У вас нет доступа к команде {command_name}")
            return

        # ДЛЯ КОМАНД, КОТОРЫЕ ДОЛЖНЫ ВЫПОЛНЯТЬСЯ (не показывать подсказку)
        if command_name in ['allsurveys', 'syncjira']:
            # Эти команды должны выполняться, а не показывать подсказку
            await handle_menu_command(update, context, command_name, args)
        else:
            # Для остальных команд показываем подсказку
            command_descriptions = {
                'profile': 'Чтобы посмотреть профиль, введите команду:',
                'help': 'Чтобы получить справку, введите команду:',
                'syncjira': 'Чтобы синхронизировать с Jira, введите команду:',
                'report': 'Чтобы получить отчеты, введите команду:',
            }

            if command_name in command_descriptions:
                await query.edit_message_text(
                    f"{command_descriptions[command_name]}\n\n`/{command_name}`",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    f"Чтобы выполнить это действие, введите команду:\n\n`/{command_name}`",
                    parse_mode='Markdown'
                )
    else:
        return


async def handle_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              command_name: str, args: list = None):
    """Универсальный обработчик команд из меню"""
    query = update.callback_query

    # Команды, которые ДОЛЖНЫ ВЫПОЛНЯТЬСЯ, а не показывать подсказку
    execute_commands = ['allsurveys', 'syncjira', 'profile', 'help']

    if command_name not in execute_commands:
        # Для остальных команд показываем подсказку
        command_descriptions = {
            'sendsurvey': 'Чтобы создать опрос, введите команду:',
            'response': 'Чтобы ответить на опрос, введите команду:',
            'addresponse': 'Чтобы дополнить ответ, введите команду:',
            'report': 'Чтобы получить отчеты, введите команду:',
        }

        description = command_descriptions.get(command_name,
                                               f"Чтобы выполнить это действие, введите команду:")

        await query.edit_message_text(
            f"{description}\n\n`/{command_name}`",
            parse_mode='Markdown'
        )
        return

    # Маппинг команд на функции (для выполнения)
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


async def survey_create_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки создания опроса"""
    query = update.callback_query
    await query.answer()

    user_role = context.user_data.get('user_role')
    role_category = get_role_category(user_role) if user_role else None

    if role_category != 'CEO':
        await query.edit_message_text("Только руководители могут создавать опросы.")
        return

    await query.edit_message_text(
        "Чтобы создать опрос, введите команду:\n\n"
        "`/sendsurvey`\n\n"
        "Эта команда запустит процесс создания и отправки нового опроса.",
        parse_mode='Markdown'
    )


async def show_main_menu(query, role_category):
    """Показать главное меню"""
    if role_category == 'CEO':
        keyboard = [
            [
                InlineKeyboardButton("Отчеты", callback_data="menu_reports"),
                InlineKeyboardButton("Опросы", callback_data="menu_surveys")
            ],
            [
                InlineKeyboardButton("Ответить на опрос", callback_data="menu_response"),
                InlineKeyboardButton("Дополнить ответ", callback_data="menu_addresponse")
            ],
            [
                InlineKeyboardButton("Синхронизация", callback_data="menu_sync"),
                InlineKeyboardButton("Профиль", callback_data="menu_profile")
            ],
            [
                InlineKeyboardButton("Помощь", callback_data="menu_help"),
                InlineKeyboardButton("Закрыть", callback_data="menu_close")
            ]
        ]
    else:
        # Для всех остальных пользователей
        keyboard = [
            [
                InlineKeyboardButton("Ответить на опрос", callback_data="menu_response"),
                InlineKeyboardButton("Дополнить ответ", callback_data="menu_addresponse")
            ],
            [
                InlineKeyboardButton("Профиль", callback_data="menu_profile"),
                InlineKeyboardButton("Помощь", callback_data="menu_help")
            ],
            [
                InlineKeyboardButton("✖Закрыть", callback_data="menu_close")
            ]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📱 **Главное меню**\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_surveys_menu(query):
    """Показать меню опросов"""
    keyboard = [
        [
            InlineKeyboardButton("Создать опрос", callback_data="survey_create"),
            InlineKeyboardButton("Просмотреть опросы", callback_data="survey_list")
        ],
        [
            InlineKeyboardButton("Назад", callback_data="menu_back")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Меню опросов\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def setup_bot_commands(application):
    """Настроить команды бота для меню"""
    base_commands = [
        ("start", "Начать работу с ботом"),
        ("menu", "Открыть меню команд"),
        ("help", "Показать справку"),
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
        commands = [
            ("start", "Начать работу с ботом"),
            ("help", "Показать справку"),
            ("cancel", "Отменить текущую операцию"),
        ]
    else:
        from tg_bot.config.roles_config import get_role_category
        role_category = get_role_category(user_role)

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
            ceo_commands = [
                ("sendsurvey", "Создать и отправить опрос"),
                ("allsurveys", "Просмотреть созданные опросы"),
                ("syncjira", "Синхронизировать данные с Jira"),
                ("report", "Информация об отчетах"),
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
    application.add_handler(CallbackQueryHandler(survey_create_handler, pattern="^survey_create$"))  # Новый обработчик
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^survey_"))
