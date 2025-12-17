import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, \
    CallbackQueryHandler

from tg_bot.config.roles_config import get_role_category
from tg_bot.database.models import SurveyModel, ResponseModel, UserModel
from datetime import datetime, timedelta
import re
from tg_bot.config.constants import (
    AWAITING_SURVEY_QUESTION,
    AWAITING_SURVEY_TIME,
    AWAITING_SURVEY_SELECTION,
    AWAITING_SURVEY_RESPONSE_PART, SURVEY_PAGINATION_PREFIX, AWAITING_SURVEY_TARGET, AWAITING_SURVEY_SUBTARGET
)
from tg_bot.config.texts import SURVEY_TEXTS, GENERAL_TEXTS
from tg_bot.handlers.survey_target_handlers import show_survey_target_selection, handle_survey_target_selection, \
    handle_survey_subtarget_selection
from tg_bot.services.pagination_utils import PaginationUtils
from tg_bot.services.validators import Validator

logger = logging.getLogger(__name__)


async def handle_survey_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка вопроса для опроса"""
    question = update.message.text.strip()

    # Используем централизованный валидатор
    is_valid, error_msg = Validator.validate_survey_question(question)

    if not is_valid:
        await update.message.reply_text(f"{error_msg}. Попробуйте снова:")
        return AWAITING_SURVEY_QUESTION

    context.user_data['survey_question'] = question

    # Показываем выбор получателей через кнопки
    return await show_survey_target_selection(update, context)


async def cancel_survey_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ответа на опрос"""
    # Проверяем, есть ли части ответа
    parts_count = len(context.user_data.get('response_parts', []))

    if parts_count > 0:
        await update.message.reply_text(
            f"Ответ отменен. Удалено {parts_count} частей ответа."
        )
    else:
        await update.message.reply_text(
            SURVEY_TEXTS['response_cancelled']
        )

    # Очищаем данные
    for key in ['current_survey_id', 'current_survey_question',
                'current_survey_datetime', 'awaiting_survey_response',
                'available_surveys', 'awaiting_survey_selection',
                'response_parts', 'pagination_surveys']:
        context.user_data.pop(key, None)

    return ConversationHandler.END


async def sendsurvey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать создание опроса"""
    # Проверяем, что пользователь из категории руководителей
    user_role = context.user_data.get('user_role')
    role_category = get_role_category(user_role) if user_role else None

    if role_category != 'CEO':
        response_text = GENERAL_TEXTS['survey_creation_permission']
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return ConversationHandler.END

    # Проверяем, вызвана ли команда из меню
    if hasattr(update, 'callback_query') and update.callback_query:
        response_text = SURVEY_TEXTS['create_welcome']
        await update.callback_query.edit_message_text(response_text)
        # Нужно сохранить message_id для продолжения диалога
        context.user_data['menu_survey_message_id'] = update.callback_query.message.message_id
    else:
        await update.message.reply_text(SURVEY_TEXTS['create_welcome'])

    context.user_data['creating_survey'] = True
    return AWAITING_SURVEY_QUESTION


async def handle_survey_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени отправки"""
    time_input = update.message.text.strip().lower()

    now = datetime.now()

    try:
        if time_input == 'сейчас':
            survey_datetime = now + timedelta(seconds=10)
            schedule_type = "немедленно"
        elif time_input.startswith('сегодня'):
            time_match = re.search(r'(\d{1,2}):(\d{2})', time_input)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                survey_datetime = datetime(now.year, now.month, now.day, hour, minute)
                schedule_type = "сегодня"
            else:
                raise ValueError("Неверный формат времени")
        elif time_input.startswith('завтра'):
            time_match = re.search(r'(\d{1,2}):(\d{2})', time_input)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                tomorrow = now + timedelta(days=1)
                survey_datetime = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute)
                schedule_type = "завтра"
            else:
                raise ValueError("Неверный формат времени")
        else:
            # Пытаемся распарсить как полную дату
            try:
                survey_datetime = datetime.strptime(time_input, '%Y-%m-%d %H:%M')
                schedule_type = "по расписанию"
            except ValueError:
                try:
                    survey_datetime = datetime.strptime(time_input, '%d.%m.%Y %H:%M')
                    schedule_type = "по расписанию"
                except ValueError:
                    raise ValueError("Неверный формат даты")

        # Проверяем, что время не в прошлом (кроме "сейчас")
        if time_input != 'сейчас' and survey_datetime < now:
            await update.message.reply_text(SURVEY_TEXTS['past_time'])
            return AWAITING_SURVEY_TIME

        # Сохраняем в контекст
        context.user_data['survey_datetime'] = survey_datetime
        context.user_data['schedule_type'] = schedule_type

        # Создаем опрос в БД
        return await create_survey_in_db(update, context)

    except Exception as e:
        await update.message.reply_text(
            SURVEY_TEXTS['invalid_time'].format(error=str(e))
        )
        return AWAITING_SURVEY_TIME


async def create_survey_in_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание опроса в БД"""
    # Формируем данные для опроса
    survey_data = {
        'datetime': context.user_data['survey_datetime'],
        'question': context.user_data['survey_question'],
        'role': context.user_data.get('survey_role'),  # Может быть None для "всем"
        'state': 'active'
    }

    # Создаем опрос в БД
    survey_id = SurveyModel.create_survey(survey_data)

    if survey_id:
        # Формируем информационное сообщение
        role_display = context.user_data['survey_role_display']
        users_count = context.user_data['target_users_count']
        schedule_time = context.user_data['survey_datetime'].strftime('%d.%m.%Y %H:%M')
        schedule_type = context.user_data['schedule_type']

        await update.message.reply_text(
            f"Опрос успешно создан!\n\n"
            f"ID опроса: {survey_id}\n"
            f"Вопрос: {context.user_data['survey_question']}\n"
            f"Получатели: {role_display} ({users_count} чел.)\n"
            f"Отправка: {schedule_time} ({schedule_type})\n\n"
            f"Опрос будет отправлен автоматически в указанное время."
        )

        # Добавляем опрос в планировщик
        if hasattr(context, 'bot_data') and 'survey_scheduler' in context.bot_data:
            survey_scheduler = context.bot_data['survey_scheduler']

            # Всегда добавляем в планировщик, он сам решит когда отправлять
            await survey_scheduler.add_new_survey(survey_id, context.user_data['survey_datetime'])
        else:
            # Fallback
            logger.warning(f"Survey scheduler not available in bot_data for survey {survey_id}")

    else:
        await update.message.reply_text(SURVEY_TEXTS['survey_error'])

    # Очищаем данные
    for key in ['creating_survey', 'survey_question', 'survey_role',
                'survey_role_display', 'survey_datetime', 'target_users_count',
                'schedule_type', 'survey_target']:
        context.user_data.pop(key, None)

    return ConversationHandler.END


async def handle_survey_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора опроса (с учетом пагинации) - ввод номера сообщением"""
    selection_text = update.message.text.strip()

    try:
        selection_num = int(selection_text)
    except ValueError:
        await update.message.reply_text(
            SURVEY_TEXTS['invalid_survey_number']
        )
        return AWAITING_SURVEY_SELECTION

    # Получаем опросы из пагинации
    pagination_data = context.user_data.get('pagination_surveys', {})
    all_surveys = pagination_data.get('items', [])

    if not all_surveys:
        # Fallback: получаем опросы старым способом
        user_id = context.user_data.get('user_id')
        user_role = context.user_data.get('user_role')

        active_surveys_for_role = SurveyModel.get_surveys_for_role(user_role)
        active_surveys_for_all = SurveyModel.get_surveys_for_role(None)
        all_surveys = active_surveys_for_role + active_surveys_for_all

        # Фильтруем
        filtered_surveys = []
        for survey in all_surveys:
            existing_response = ResponseModel.get_user_response(survey['id_survey'], user_id)
            if not existing_response:
                filtered_surveys.append(survey)

        all_surveys = filtered_surveys

    if not 1 <= selection_num <= len(all_surveys):
        await update.message.reply_text(
            SURVEY_TEXTS['survey_out_of_range'].format(count=len(all_surveys))
        )
        return AWAITING_SURVEY_SELECTION

    selected_survey = all_surveys[selection_num - 1]

    context.user_data['current_survey_id'] = selected_survey['id_survey']
    context.user_data['current_survey_question'] = selected_survey['question']
    context.user_data['current_survey_datetime'] = selected_survey['datetime']
    context.user_data['awaiting_survey_response'] = True
    context.user_data['response_parts'] = []

    # Очищаем данные пагинации
    context.user_data.pop('pagination_surveys', None)

    # Определяем, для кого опрос
    target = selected_survey['role'] if selected_survey['role'] else "все пользователи"

    await update.message.reply_text(
        f"Опрос #{selected_survey['id_survey']}\n"
        f"Дата: {selected_survey['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
        f"Для: {target}\n\n"
        f"Вопрос: {selected_survey['question']}\n\n"
        f"Когда закончите, отправьте команду /done для сохранения ответа\n"
        f"Или /cancel для отмены."
    )

    return AWAITING_SURVEY_RESPONSE_PART


async def finish_response_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение ответа на опрос (команда /done)"""
    if 'response_parts' not in context.user_data or not context.user_data['response_parts']:
        await update.message.reply_text(
            "Вы не отправили ни одной части ответа.\n"
            "Ответ не сохранен."
        )
        return await cancel_survey_response(update, context)

    # Объединяем все части ответа
    full_response = "\n".join(context.user_data['response_parts'])

    if len(full_response) < 3:
        await update.message.reply_text(
            "Ответ должен содержать минимум 3 символа. Попробуйте снова:"
        )
        return AWAITING_SURVEY_RESPONSE_PART

    # Получаем информацию об опросе
    survey_id = context.user_data['current_survey_id']
    question = context.user_data.get('current_survey_question', 'Без вопроса')
    survey_date = context.user_data.get('current_survey_datetime')

    # Сохраняем ответ в БД
    response_data = {
        'id_survey': survey_id,
        'id_user': context.user_data['user_id'],
        'answer': full_response
    }

    response_id = ResponseModel.save_response(response_data)

    if response_id:
        # Форматируем дату для сообщения
        date_str = ""
        if survey_date:
            if isinstance(survey_date, datetime):
                date_str = survey_date.strftime('%d.%m.%Y %H:%M')
            elif isinstance(survey_date, str):
                date_str = survey_date
            else:
                date_str = str(survey_date)

        # ФОРМИРУЕМ ЧИСТОЕ ФИНАЛЬНОЕ СООБЩЕНИЕ
        response_message = (
            f"Ваш ответ сохранен!\n\n"
            f"Опрос #{survey_id}\n"
            f"Вопрос: {question}\n"
            f"Дата опроса: {date_str}\n\n"
            f"Ваш ответ:\n"
            f"{full_response}"
        )

        # Если ответ слишком длинный, разбиваем на части
        if len(response_message) > 4000:
            # Отправляем заголовок
            header = (
                f"Ваш ответ сохранен!\n\n"
                f"Опрос #{survey_id}\n"
                f"Вопрос: {question}\n"
                f"Дата опроса: {date_str}\n\n"
                f"Ваш ответ:"
            )
            await update.message.reply_text(header)

            # Отправляем ответ по частям
            response_lines = full_response.split('\n')
            current_part = ""

            for line in response_lines:
                if len(current_part) + len(line) + 1 > 4000:
                    await update.message.reply_text(current_part)
                    current_part = line + "\n"
                    await asyncio.sleep(0.3)
                else:
                    current_part += line + "\n"

            if current_part:
                await update.message.reply_text(current_part)
        else:
            await update.message.reply_text(response_message)
    else:
        await update.message.reply_text(SURVEY_TEXTS['answer_error'])

    # Очищаем данные
    for key in ['current_survey_id', 'current_survey_question',
                'current_survey_datetime', 'awaiting_survey_response',
                'response_parts', 'available_surveys', 'awaiting_survey_selection',
                'pagination_surveys']:
        context.user_data.pop(key, None)

    return ConversationHandler.END


async def handle_response_part(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка части ответа на опрос (молча, без уведомлений)"""
    response_text = update.message.text.strip()

    # Игнорируем команды (их обработает ConversationHandler)
    if response_text.startswith('/'):
        # Пропускаем обработку, команды обработаются в fallbacks
        return AWAITING_SURVEY_RESPONSE_PART

    # Инициализируем список частей, если его нет
    if 'response_parts' not in context.user_data:
        context.user_data['response_parts'] = []

    # Добавляем часть ответа (без всяких уведомлений)
    context.user_data['response_parts'].append(response_text)

    return AWAITING_SURVEY_RESPONSE_PART


async def cancel_survey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания опроса"""
    # Очищаем все данные опроса
    for key in ['creating_survey', 'survey_question', 'survey_role',
                'survey_role_display', 'survey_datetime', 'target_users_count',
                'schedule_type', 'current_survey_id', 'current_survey_question',
                'awaiting_survey_response']:
        context.user_data.pop(key, None)

    await update.message.reply_text(SURVEY_TEXTS['survey_cancelled'])

    return ConversationHandler.END


async def response_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ответа на опрос с пагинацией"""
    user_id = context.user_data.get('user_id')
    user_role = context.user_data.get('user_role')

    if not user_role:
        response_text = "Сначала авторизуйтесь с помощью /start"
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return ConversationHandler.END

    from tg_bot.config.constants import RESPONSE_PERIOD_DAYS
    period_days = RESPONSE_PERIOD_DAYS
    date_from = datetime.now() - timedelta(days=period_days)

    # Получаем активные опросы с ограничением по дате
    active_surveys_for_role = SurveyModel.get_surveys_for_role_since(user_role, date_from)
    active_surveys_for_all = SurveyModel.get_surveys_for_role_since(None, date_from)
    all_active_surveys = active_surveys_for_role + active_surveys_for_all

    if not all_active_surveys:
        response_text = SURVEY_TEXTS['no_active_surveys']
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return

    # Фильтруем опросы, на которые пользователь еще не отвечал
    unanswered_surveys = []
    for survey in all_active_surveys:
        existing_response = ResponseModel.get_user_response(survey['id_survey'], user_id)
        if not existing_response:
            unanswered_surveys.append(survey)

    if not unanswered_surveys:
        response_text = SURVEY_TEXTS['all_surveys_answered']
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return

    # Сохраняем опросы для пагинации
    context.user_data['pagination_surveys'] = {
        'items': unanswered_surveys,
        'type': 'response'
    }

    # Логируем для отладки
    logger.info(f"Пагинация создана для /response: {len(unanswered_surveys)} опросов за 2 недели")

    # Всегда показываем пагинацию (независимо от вызова через меню или команду)
    if hasattr(update, 'callback_query') and update.callback_query:
        # Через меню - показываем первую страницу
        await _show_response_page(query=update.callback_query, context=context, page=0)
    else:
        # Через текстовую команду - также показываем первую страницу
        await _send_response_page(message_obj=update.message, context=context, page=0)

    return AWAITING_SURVEY_SELECTION


async def _show_response_page(query, context, page=0):
    """Показать страницу с пагинацией (для меню)"""
    user_data = context.user_data
    items = user_data.get('pagination_surveys', {}).get('items', [])

    if not items:
        await query.edit_message_text("Нет доступных опросов.")
        return

    page_items, current_page, total_pages = PaginationUtils.get_page_items(items, page)

    # Форматируем сообщение с указанием периода
    message = PaginationUtils.format_page_with_numbers(
        page_items, current_page, total_pages, "ДОСТУПНЫЕ ОПРОСЫ (2 недели)"
    )

    # Создаем клавиатуру навигации
    keyboard = PaginationUtils.create_pagination_navigation(
        page=current_page,
        total_pages=total_pages,
        callback_prefix=SURVEY_PAGINATION_PREFIX
    )

    await query.edit_message_text(
        message,
        reply_markup=keyboard
    )


async def _send_response_page(message_obj, context, page=0):
    """Отправить страницу (для текстовой команды)"""
    user_data = context.user_data
    items = user_data.get('pagination_surveys', {}).get('items', [])

    if not items:
        await message_obj.reply_text("Нет доступных опросов.")
        return

    page_items, current_page, total_pages = PaginationUtils.get_page_items(items, page)

    # Форматируем сообщение
    message = PaginationUtils.format_page_with_numbers(
        page_items, current_page, total_pages, "📋 ДОСТУПНЫЕ ОПРОСЫ"
    )

    # Создаем клавиатуру навигации
    keyboard = PaginationUtils.create_pagination_navigation(
        page=current_page,
        total_pages=total_pages,
        callback_prefix=SURVEY_PAGINATION_PREFIX
    )

    # Отправляем сообщение с клавиатурой
    await message_obj.reply_text(
        message,
        reply_markup=keyboard
    )


survey_response_conversation = ConversationHandler(
    entry_points=[CommandHandler('response', response_command)],
    states={
        AWAITING_SURVEY_SELECTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_survey_selection)
        ],
        AWAITING_SURVEY_RESPONSE_PART: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response_part)
        ],
    },
    fallbacks=[
        CommandHandler('done', finish_response_command),
        CommandHandler('cancel', cancel_survey_response),
        CommandHandler('stop', cancel_survey_response),
    ],
)

survey_creation_conversation = ConversationHandler(
    entry_points=[CommandHandler('sendsurvey', sendsurvey_command)],
    states={
        AWAITING_SURVEY_QUESTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_survey_question)
        ],
        AWAITING_SURVEY_TARGET: [
            CallbackQueryHandler(handle_survey_target_selection, pattern=f"^survey_target_")
        ],
        AWAITING_SURVEY_SUBTARGET: [
            CallbackQueryHandler(handle_survey_subtarget_selection, pattern=f"^survey_subtarget_")
        ],
        AWAITING_SURVEY_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_survey_time)
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel_survey)],
    per_user=True,
    per_chat=True
)
