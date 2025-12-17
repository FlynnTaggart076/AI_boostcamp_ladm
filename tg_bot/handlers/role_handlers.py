# -*- coding: utf-8 -*-
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler

from tg_bot.config.constants import (
    AWAITING_ROLE, AWAITING_SUBROLE,
    CATEGORY_SELECTION_PREFIX, SUBTYPE_SELECTION_PREFIX
)
from tg_bot.config.texts import ROLE_SELECTION_TEXTS, get_category_display, get_role_display_with_icon
from tg_bot.config.roles_config import get_worker_subtypes, get_ceo_subtypes, ALL_ROLES

logger = logging.getLogger(__name__)


async def show_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор категории роли (CEO/worker) через кнопки"""
    keyboard = [
        [
            InlineKeyboardButton("👔 Руководители", callback_data=f"{CATEGORY_SELECTION_PREFIX}CEO"),
            InlineKeyboardButton("🔧 Работники", callback_data=f"{CATEGORY_SELECTION_PREFIX}worker")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            ROLE_SELECTION_TEXTS['choose_category'],
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            ROLE_SELECTION_TEXTS['choose_category'],
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    return AWAITING_ROLE


async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора категории роли"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    category = callback_data.replace(CATEGORY_SELECTION_PREFIX, "")

    # Сохраняем выбранную категорию
    context.user_data['selected_category'] = category

    # Показываем выбор конкретной роли в категории
    if category == 'CEO':
        subtypes = get_ceo_subtypes()
        message_text = ROLE_SELECTION_TEXTS['choose_ceo_subtype']
    else:  # worker
        subtypes = get_worker_subtypes()
        message_text = ROLE_SELECTION_TEXTS['choose_worker_subtype']

    # Создаем кнопки для подтипов
    keyboard = []
    row = []
    for i, subtype in enumerate(subtypes):
        role_display = get_role_display_with_icon(subtype)
        row.append(InlineKeyboardButton(role_display, callback_data=f"{SUBTYPE_SELECTION_PREFIX}{subtype}"))

        # Разбиваем на ряды по 2 кнопки
        if len(row) == 2 or i == len(subtypes) - 1:
            keyboard.append(row)
            row = []

    # Кнопка "Назад" для возврата к выбору категории
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"{CATEGORY_SELECTION_PREFIX}back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ROLE_SELECTION_TEXTS['category_selected'].format(category=get_category_display(category))}\n\n{message_text}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return AWAITING_SUBROLE


async def handle_subtype_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора конкретной роли"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == f"{CATEGORY_SELECTION_PREFIX}back":
        # Возврат к выбору категории
        return await show_role_selection(update, context)

    # Извлекаем выбранную роль
    selected_role = callback_data.replace(SUBTYPE_SELECTION_PREFIX, "")

    # Проверяем, что роль валидна
    if selected_role not in ALL_ROLES:
        await query.edit_message_text(f"❌ Ошибка: недопустимая роль '{selected_role}'")
        return AWAITING_SUBROLE

    # Сохраняем выбранную роль
    context.user_data['selected_role'] = selected_role

    # Получаем отображаемое имя роли
    role_display = get_role_display_with_icon(selected_role)

    # Показываем подтверждение
    await query.edit_message_text(
        ROLE_SELECTION_TEXTS['role_confirmed'].format(role_display=role_display),
        parse_mode='Markdown'
    )

    # Возвращаем управление в основной процесс регистрации
    # Продолжаем регистрацию с выбранной ролью
    from tg_bot.handlers.auth_handlers import complete_registration_with_role
    return await complete_registration_with_role(update, context, selected_role)


def setup_role_handlers(application):
    """Настройка обработчиков выбора ролей"""
    application.add_handler(CallbackQueryHandler(
        handle_category_selection,
        pattern=f"^{CATEGORY_SELECTION_PREFIX}"
    ))
    application.add_handler(CallbackQueryHandler(
        handle_subtype_selection,
        pattern=f"^{SUBTYPE_SELECTION_PREFIX}"
    ))
    logger.info("Обработчики выбора ролей настроены")
