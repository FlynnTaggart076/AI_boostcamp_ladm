# -*- coding: utf-8 -*-
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from tg_bot.services.pagination_utils import PaginationUtils
from tg_bot.config.constants import (
    SURVEY_PAGINATION_PREFIX,
    ADD_RESPONSE_PAGINATION_PREFIX,
    ALLSURVEYS_PAGINATION_PREFIX
)

logger = logging.getLogger(__name__)


async def handle_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единый обработчик пагинации для всех типов"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    # Определяем тип пагинации по префиксу
    if callback_data.startswith(SURVEY_PAGINATION_PREFIX):
        await _handle_pagination_navigation(
            query, context, callback_data, SURVEY_PAGINATION_PREFIX,
            'pagination_surveys', "📋 ДОСТУПНЫЕ ОПРОСЫ"
        )
    elif callback_data.startswith(ADD_RESPONSE_PAGINATION_PREFIX):
        await _handle_pagination_navigation(
            query, context, callback_data, ADD_RESPONSE_PAGINATION_PREFIX,
            'pagination_addresponse', "📝 ОТВЕЧЕННЫЕ ОПРОСЫ"
        )
    elif callback_data.startswith(ALLSURVEYS_PAGINATION_PREFIX):
        await _handle_pagination_navigation(
            query, context, callback_data, ALLSURVEYS_PAGINATION_PREFIX,
            'pagination_allsurveys', "📊 ВСЕ АКТИВНЫЕ ОПРОСЫ"
        )
    else:
        logger.warning(f"Неизвестный callback_data пагинации: {callback_data}")


async def _handle_pagination_navigation(query, context, callback_data, prefix, data_key, title):
    """Обработка навигации по страницам для всех типов пагинации"""
    # Убираем префикс
    action = callback_data[len(prefix):]

    if action == "close":
        await query.edit_message_text("Просмотр закрыт.")
        # Очищаем данные пагинации для этого типа
        context.user_data.pop(data_key, None)
        return

    if action == "info":
        await query.answer("Используйте кнопки для навигации между страницами")
        return

    # Обработка номера страницы (например: "0", "1", "2")
    if action.isdigit() or (action[0] == '-' and action[1:].isdigit()):
        page = int(action)
        await _show_pagination_page(query, context, page, data_key, title, prefix)
        return

    logger.warning(f"Неизвестный action в callback_data: {action}")


async def _show_pagination_page(query, context, page, data_key, title, prefix):
    """Показать страницу пагинации"""
    user_data = context.user_data
    items_data = user_data.get(data_key, {})
    items = items_data.get('items', [])

    if not items:
        await query.edit_message_text("Нет элементов для отображения.")
        return

    page_items, current_page, total_pages = PaginationUtils.get_page_items(items, page)

    # Форматируем сообщение
    message = PaginationUtils.format_page_with_numbers(page_items, current_page, total_pages, title)

    # Создаем клавиатуру навигации
    keyboard = PaginationUtils.create_pagination_navigation(
        page=current_page,
        total_pages=total_pages,
        callback_prefix=prefix
    )

    await query.edit_message_text(
        message,
        reply_markup=keyboard
    )


def setup_pagination_handlers(application):
    """Настроить обработчики пагинации"""
    # Обработчик для всех типов пагинации
    pattern = f"^({SURVEY_PAGINATION_PREFIX}|{ADD_RESPONSE_PAGINATION_PREFIX}|{ALLSURVEYS_PAGINATION_PREFIX})"

    application.add_handler(CallbackQueryHandler(
        handle_pagination_callback,
        pattern=pattern
    ))
    logger.info("Обработчики пагинации настроены")
