# -*- coding: utf-8 -*-
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler

from tg_bot.config.constants import (
    AWAITING_SURVEY_TARGET, AWAITING_SURVEY_SUBTARGET,
    SURVEY_TARGET_PREFIX, SURVEY_SUBTARGET_PREFIX
)
from tg_bot.config.texts import get_role_display_with_icon, get_category_display
from tg_bot.config.roles_config import get_worker_subtypes, get_ceo_subtypes
from tg_bot.database.models import UserModel

logger = logging.getLogger(__name__)


async def show_survey_target_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор получателей опроса (всем/CEO/worker) через кнопки"""
    # Проверяем количество пользователей для каждой категории
    all_users = UserModel.get_all_users_with_tg_id()
    ceo_users = UserModel.get_users_by_role('CEO')
    worker_users = UserModel.get_users_by_role('worker')

    keyboard = [
        [
            InlineKeyboardButton(f"Всем пользователям ({len(all_users)})",
                                 callback_data=f"{SURVEY_TARGET_PREFIX}all"),
        ],
        [
            InlineKeyboardButton(f"Руководители ({len(ceo_users)})",
                                 callback_data=f"{SURVEY_TARGET_PREFIX}CEO"),
            InlineKeyboardButton(f"Работники ({len(worker_users)})",
                                 callback_data=f"{SURVEY_TARGET_PREFIX}worker")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        "Выберите кому отправить опрос:\n\n"
        "Выберите категорию получателей:"
    )

    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    return AWAITING_SURVEY_TARGET


async def handle_survey_target_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора категории получателей"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    target = callback_data.replace(SURVEY_TARGET_PREFIX, "")

    # Сохраняем выбранную категорию
    context.user_data['survey_target'] = target

    if target == 'all':
        # Если выбрали "всем", сразу переходим к выбору времени
        context.user_data['survey_role'] = None  # NULL в БД означает "для всех"
        context.user_data['survey_role_display'] = 'всем пользователям'

        # Считаем количество пользователей
        all_users = UserModel.get_all_users_with_tg_id()
        context.user_data['target_users_count'] = len(all_users)

        await query.edit_message_text(
            f"Выбрано: Всем пользователям ({len(all_users)} пользователей)\n\n"
            f"Теперь укажите время отправки опроса в формате:\n"
            f"• 'сегодня 14:30'\n"
            f"• 'завтра 09:00'\n"
            f"• '2024-01-20 18:00'\n"
            f"• 'сейчас'",
            parse_mode='Markdown'
        )

        from tg_bot.handlers.survey_handlers import AWAITING_SURVEY_TIME
        return AWAITING_SURVEY_TIME

    else:
        # Показываем выбор конкретной роли в категории
        if target == 'CEO':
            subtypes = get_ceo_subtypes()
            message_text = "Выберите конкретную роль руководителя:"
        else:  # worker
            subtypes = get_worker_subtypes()
            message_text = "Выберите конкретную роль работника:"

        # Создаем кнопки для подтипов
        keyboard = []
        for subtype in subtypes:
            role_display = get_role_display_with_icon(subtype)

            # Считаем количество пользователей с этой ролью
            users = UserModel.get_users_by_role(subtype)
            count_text = f" ({len(users)} чел.)"

            keyboard.append([
                InlineKeyboardButton(
                    f"{role_display}{count_text}",
                    callback_data=f"{SURVEY_SUBTARGET_PREFIX}{subtype}"
                )
            ])

        # Кнопка "Назад" для возврата к выбору категории - УНИКАЛЬНЫЙ ПРЕФИКС
        keyboard.append([
            InlineKeyboardButton("Назад к выбору категории",
                                 callback_data=f"{SURVEY_TARGET_PREFIX}back_to_category")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Категория: {get_category_display(target)}\n\n{message_text}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        return AWAITING_SURVEY_SUBTARGET


async def handle_survey_subtarget_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора конкретной роли получателей"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    # Проверяем кнопку "Назад" - УНИКАЛЬНЫЙ ПРЕФИКС
    if callback_data == f"{SURVEY_TARGET_PREFIX}back_to_category":
        # Возврат к выбору категории
        return await show_survey_target_selection(update, context)

    # Извлекаем выбранную роль
    selected_role = callback_data.replace(SURVEY_SUBTARGET_PREFIX, "")

    # Сохраняем выбранную роль
    context.user_data['survey_role'] = selected_role
    context.user_data['survey_role_display'] = get_role_display_with_icon(selected_role)

    # Считаем количество пользователей с этой ролью
    users = UserModel.get_users_by_role(selected_role)
    context.user_data['target_users_count'] = len(users)

    if users:
        await query.edit_message_text(
            f"Выбрано: {get_role_display_with_icon(selected_role)} "
            f"({len(users)} пользователей)\n\n"
            f"Теперь укажите время отправки опроса в формате:\n"
            f"• 'сегодня 14:30'\n"
            f"• 'завтра 09:00'\n"
            f"• '2024-01-20 18:00'\n"
            f"• 'сейчас'",
            parse_mode='Markdown'
        )

        from tg_bot.handlers.survey_handlers import AWAITING_SURVEY_TIME
        return AWAITING_SURVEY_TIME
    else:
        # Если нет пользователей с этой ролью
        await query.edit_message_text(
            f"Нет пользователей с ролью: {get_role_display_with_icon(selected_role)}\n\n"
            f"Выберите другую роль:"
        )

        # Возвращаем к выбору роли
        target = context.user_data.get('survey_target', 'CEO')
        if target == 'CEO':
            subtypes = get_ceo_subtypes()
        else:
            subtypes = get_worker_subtypes()

        # Создаем кнопки заново
        keyboard = []
        for subtype in subtypes:
            role_display = get_role_display_with_icon(subtype)
            users_count = len(UserModel.get_users_by_role(subtype))
            count_text = f" ({users_count} чел.)"

            keyboard.append([
                InlineKeyboardButton(
                    f"{role_display}{count_text}",
                    callback_data=f"{SURVEY_SUBTARGET_PREFIX}{subtype}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("Назад к выбору категории",
                                 callback_data=f"{SURVEY_TARGET_PREFIX}back_to_category")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Выберите роль с пользователями:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        return AWAITING_SURVEY_SUBTARGET


def setup_survey_target_handlers(application):
    """Настройка обработчиков выбора получателей опроса"""
    application.add_handler(CallbackQueryHandler(
        handle_survey_target_selection,
        pattern=f"^{SURVEY_TARGET_PREFIX}(?!back_to_category)"  # Исключаем кнопку "Назад"
    ))
    application.add_handler(CallbackQueryHandler(
        handle_survey_subtarget_selection,
        pattern=f"^{SURVEY_SUBTARGET_PREFIX}"
    ))
    # Отдельный обработчик для кнопки "Назад"
    application.add_handler(CallbackQueryHandler(
        handle_survey_subtarget_selection,
        pattern=f"^{SURVEY_TARGET_PREFIX}back_to_category$"
    ))
    logger.info("Обработчики выбора получателей опроса настроены")
