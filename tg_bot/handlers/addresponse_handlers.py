# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from tg_bot.config.constants import (
    AWAITING_ADD_RESPONSE_SELECTION,
    AWAITING_ADD_RESPONSE_PART, ADD_RESPONSE_PAGINATION_PREFIX
)
from tg_bot.database.connection import db_connection
from tg_bot.database.models import ResponseModel
from tg_bot.services.pagination_utils import PaginationUtils

logger = logging.getLogger(__name__)


async def handle_add_response_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора опроса для дополнения (ввод номера сообщением)"""
    selection_text = update.message.text.strip()

    try:
        selection_num = int(selection_text)
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите корректный номер опроса. Попробуйте снова:"
        )
        return AWAITING_ADD_RESPONSE_SELECTION

    pagination_data = context.user_data.get('pagination_addresponse', {})
    all_surveys = pagination_data.get('items', [])

    if not all_surveys:
        all_surveys = context.user_data.get('available_surveys_add', [])

    if not 1 <= selection_num <= len(all_surveys):
        await update.message.reply_text(
            f"Некорректный выбор. Введите число от 1 до {len(all_surveys)}:"
        )
        return AWAITING_ADD_RESPONSE_SELECTION

    selected_survey = all_surveys[selection_num - 1]

    context.user_data['current_add_survey_id'] = selected_survey['id_survey']
    context.user_data['current_add_survey_question'] = selected_survey['question']
    context.user_data['current_add_survey_datetime'] = selected_survey['datetime']
    context.user_data['current_add_response_id'] = selected_survey['id_response']
    context.user_data['current_add_original_answer'] = selected_survey['user_answer']
    context.user_data['awaiting_add_response_part'] = True
    context.user_data['add_response_parts'] = []

    context.user_data.pop('pagination_addresponse', None)
    context.user_data.pop('available_surveys_add', None)
    context.user_data.pop('awaiting_add_response_selection', None)

    # Определяем, для кого опрос
    target = selected_survey['role'] if selected_survey['role'] else "все пользователи"

    # Формируем сообщение с текущим ответом
    current_answer = selected_survey['user_answer'] or "(пустой ответ)"
    current_answer_preview = current_answer[:100] + "..." if len(current_answer) > 100 else current_answer

    await update.message.reply_text(
        f"ДОПОЛНЕНИЕ ОТВЕТА\n\n"
        f"Опрос #{selected_survey['id_survey']}\n"
        f"Дата: {selected_survey['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
        f"Для: {target}\n\n"
        f"Вопрос: {selected_survey['question']}\n\n"
        f"Ваш текущий ответ:\n{current_answer_preview}\n\n"
        f"Теперь введите дополнительный текст для этого ответа.\n"
        f"Можно отправлять несколько сообщений подряд.\n\n"
        f"Когда закончите, используйте:\n"
        f"/done - сохранить дополненный ответ\n"
        f"/cancel - отменить дополнение"
    )

    return AWAITING_ADD_RESPONSE_PART


async def handle_add_response_part(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка части дополнения ответа (молча, без уведомлений)"""
    response_text = update.message.text.strip()

    # Игнорируем команды (их обработает ConversationHandler)
    if response_text.startswith('/'):
        # Пропускаем обработку, команды обработаются в fallbacks
        return AWAITING_ADD_RESPONSE_PART

    # Инициализируем список частей, если его нет
    if 'add_response_parts' not in context.user_data:
        context.user_data['add_response_parts'] = []

    # Добавляем часть ответа
    context.user_data['add_response_parts'].append(response_text)

    return AWAITING_ADD_RESPONSE_PART


async def finish_add_response_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение дополнения ответа (команда /done)"""
    if 'add_response_parts' not in context.user_data or not context.user_data['add_response_parts']:
        await update.message.reply_text(
            "Вы не отправили ни одного дополнительного сообщения.\n"
            "Ответ не обновлен."
        )
        return await cancel_add_response(update, context)

    # Объединяем все новые части ответа
    new_text = "\n".join(context.user_data['add_response_parts'])

    # Получаем оригинальный ответ
    original_answer = context.user_data.get('current_add_original_answer', '')

    # Формируем новый полный ответ (оригинал + дополнение)
    if original_answer and original_answer != "(пустой ответ)":
        full_response = f"{original_answer}\n\n[Дополнено {datetime.now().strftime('%d.%m.%Y %H:%M')}]:\n{new_text}"
    else:
        full_response = new_text

    # Получаем информацию об опросе
    survey_id = context.user_data['current_add_survey_id']
    question = context.user_data.get('current_add_survey_question', 'Без вопроса')
    response_id = context.user_data.get('current_add_response_id')

    # Сохраняем обновленный ответ в БД
    if response_id:
        # Обновляем существующий ответ
        success = update_existing_response(response_id, full_response)
    else:
        # Создаем новый ответ (на всякий случай)
        response_data = {
            'id_survey': survey_id,
            'id_user': context.user_data['user_id'],
            'answer': full_response
        }
        success = ResponseModel.save_response(response_data) is not None

    if success:
        # Формируем финальное сообщение
        await update.message.reply_text(
            f"Ответ успешно обновлен!\n\n"
            f"Опрос #{survey_id}\n"
            f"Вопрос: {question}\n\n"
            f"Ваш обновленный ответ:\n"
            f"{full_response}"
        )
    else:
        await update.message.reply_text("Ошибка обновления ответа. Попробуйте позже.")

    # Очищаем данные
    cleanup_add_response_data(context)
    return ConversationHandler.END


async def cancel_add_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена дополнения ответа"""
    parts_count = len(context.user_data.get('add_response_parts', []))

    if parts_count > 0:
        await update.message.reply_text(
            f"Дополнение ответа отменено. Удалено {parts_count} частей."
        )
    else:
        await update.message.reply_text("Дополнение ответа отменено.")

    # Очищаем данные
    cleanup_add_response_data(context)
    return ConversationHandler.END


def cleanup_add_response_data(context):
    """Очистка данных дополнения ответа"""
    keys_to_remove = [
        'current_add_survey_id',
        'current_add_survey_question',
        'current_add_survey_datetime',
        'current_add_response_id',
        'current_add_original_answer',
        'awaiting_add_response_part',
        'add_response_parts',
        'available_surveys_add',
        'awaiting_add_response_selection',
        'pagination_addresponse'  # Добавляем очистку пагинации
    ]

    for key in keys_to_remove:
        context.user_data.pop(key, None)


def update_existing_response(response_id: int, new_answer: str) -> bool:
    """Обновление существующего ответа в БД"""
    query = '''
    UPDATE responses 
    SET answer = %s
    WHERE id_response = %s
    RETURNING id_response;
    '''

    try:
        connection = db_connection.get_connection()
        if not connection:
            return False

        cursor = connection.cursor()
        cursor.execute(query, (new_answer, response_id))
        result = cursor.fetchone()
        connection.commit()

        return result is not None

    except Exception as e:
        logger.error(f"Ошибка обновления ответа: {e}", exc_info=True)
        if connection:
            connection.rollback()
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


async def addresponse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для добавления/дополнения ответа на опрос с пагинацией"""
    user_id = context.user_data.get('user_id')
    user_role = context.user_data.get('user_role')

    if not user_role:
        response_text = "Сначала авторизуйтесь с помощью /start"
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return ConversationHandler.END

    from tg_bot.config.constants import ADDRESPONSE_PERIOD_DAYS
    period_days = ADDRESPONSE_PERIOD_DAYS
    date_from = datetime.now() - timedelta(days=period_days)

    # Получаем активные опросы, на которые пользователь уже отвечал за последние 2 недели
    query_sql = '''
    SELECT 
        s.id_survey,
        s.datetime,
        s.question,
        s.role,
        s.state,
        r.id_response,
        r.answer as user_answer
    FROM surveys s
    JOIN responses r ON s.id_survey = r.id_survey
    WHERE r.id_user = %s 
      AND s.datetime >= %s  -- опросы не старше 2 недель
      AND s.state = 'active'  -- только активные опросы
    ORDER BY s.datetime DESC
    LIMIT 200;
    '''

    try:
        connection = db_connection.get_connection()
        if not connection:
            response_text = "Ошибка подключения к БД"
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(response_text)
            else:
                await update.message.reply_text(response_text)
            return ConversationHandler.END

        cursor = connection.cursor()
        cursor.execute(query_sql, (user_id, date_from))

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        surveys = []
        for row in rows:
            survey_dict = dict(zip(columns, row))
            surveys.append(survey_dict)

        # Логируем для отладки
        logger.info(f"Найдено отвеченных активных опросов за 2 недели для user_id={user_id}: {len(surveys)}")
        if surveys:
            survey_ids = [s['id_survey'] for s in surveys]
            logger.info(f"ID опросов за 2 недели: {survey_ids}")
            # Дополнительная отладочная информация
            for s in surveys:
                logger.info(f"Опрос #{s['id_survey']}: дата={s['datetime']}, статус={s['state']}")

        if not surveys:
            response_text = (
                "У вас нет отвеченных активных опросов за последние 2 недели.\n"
                "Используйте /response для ответа на новые опросы."
            )
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(response_text)
            else:
                await update.message.reply_text(response_text)
            return ConversationHandler.END

        # Сохраняем опросы для пагинации
        context.user_data['pagination_addresponse'] = {
            'items': surveys,
            'type': 'addresponse'
        }

        # Всегда показываем пагинацию
        if hasattr(update, 'callback_query') and update.callback_query:
            # Через меню
            await _show_addresponse_page(query=update.callback_query, context=context, page=0)
        else:
            # Через текстовую команду
            await _send_addresponse_page(message_obj=update.message, context=context, page=0)

        return AWAITING_ADD_RESPONSE_SELECTION

    except Exception as e:
        logger.error(f"Ошибка при получении отвеченных опросов: {e}", exc_info=True)
        response_text = "Произошла ошибка при получении данных. Попробуйте позже."
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return ConversationHandler.END
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


async def _show_addresponse_page(query, context, page=0):
    """Показать страницу с пагинацией для дополнения ответов (для меню)"""
    user_data = context.user_data
    items = user_data.get('pagination_addresponse', {}).get('items', [])

    if not items:
        await query.edit_message_text("Нет отвеченных опросов.")
        return

    page_items, current_page, total_pages = PaginationUtils.get_page_items(items, page)

    # Форматируем сообщение
    message = PaginationUtils.format_page_with_numbers(
        page_items, current_page, total_pages, "📝 ОТВЕЧЕННЫЕ ОПРОСЫ (2 недели)"
    )

    # Создаем клавиатуру навигации
    keyboard = PaginationUtils.create_pagination_navigation(
        page=current_page,
        total_pages=total_pages,
        callback_prefix=ADD_RESPONSE_PAGINATION_PREFIX
    )

    await query.edit_message_text(
        message,
        reply_markup=keyboard
    )


async def _send_addresponse_page(message_obj, context, page=0):
    """Отправить страницу для дополнения ответов (для текстовой команды)"""
    user_data = context.user_data
    items = user_data.get('pagination_addresponse', {}).get('items', [])

    if not items:
        await message_obj.reply_text("У вас нет отвеченных активных опросов за последние 2 недели.")
        return

    page_items, current_page, total_pages = PaginationUtils.get_page_items(items, page)

    # Форматируем сообщение
    message = PaginationUtils.format_page_with_numbers(
        page_items, current_page, total_pages, "📝 ОТВЕЧЕННЫЕ ОПРОСЫ (2 недели)"
    )

    # Создаем клавиатуру навигации
    keyboard = PaginationUtils.create_pagination_navigation(
        page=current_page,
        total_pages=total_pages,
        callback_prefix=ADD_RESPONSE_PAGINATION_PREFIX
    )

    await message_obj.reply_text(
        message,
        reply_markup=keyboard
    )


addresponse_conversation = ConversationHandler(
    entry_points=[CommandHandler('addresponse', addresponse_command)],
    states={
        AWAITING_ADD_RESPONSE_SELECTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_response_selection)
        ],
        AWAITING_ADD_RESPONSE_PART: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_response_part)
        ],
    },
    fallbacks=[
        CommandHandler('done', finish_add_response_command),
        CommandHandler('cancel', cancel_add_response),
        CommandHandler('stop', cancel_add_response),
    ],
)
