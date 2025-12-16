import asyncio

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from tg_bot.config.roles_config import get_role_category
from tg_bot.database.models import SurveyModel, ResponseModel, UserModel
from datetime import datetime, timedelta
import re
from tg_bot.config.constants import (
    AWAITING_SURVEY_QUESTION,
    AWAITING_SURVEY_ROLE,
    AWAITING_SURVEY_TIME,
    AWAITING_SURVEY_SELECTION,
    AWAITING_SURVEY_RESPONSE, AWAITING_SURVEY_RESPONSE_PART
)
from tg_bot.config.texts import SURVEY_TEXTS, GENERAL_TEXTS
from tg_bot.services.validators import Validator

async def handle_survey_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка вопроса для опроса"""
    question = update.message.text.strip()

    # Используем централизованный валидатор
    is_valid, error_msg = Validator.validate_survey_question(question)

    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}. Попробуйте снова:")
        return AWAITING_SURVEY_QUESTION

    context.user_data['survey_question'] = question
    await update.message.reply_text(SURVEY_TEXTS['question_saved'])
    return AWAITING_SURVEY_ROLE


async def handle_survey_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени отправки"""
    time_input = update.message.text.strip().lower()

    # Используем централизованный валидатор
    is_valid, error_msg, send_time = Validator.validate_survey_time(time_input)

    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\n" + SURVEY_TEXTS['invalid_time'])
        return AWAITING_SURVEY_TIME

    context.user_data['survey_datetime'] = send_time
    context.user_data['schedule_type'] = "немедленно" if time_input == 'сейчас' else "по расписанию"

    # Создаем опрос в БД
    return await create_survey_in_db(update, context)


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
                'response_parts']:
        context.user_data.pop(key, None)

    return ConversationHandler.END


async def sendsurvey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, что пользователь из категории руководителей
    user_role = context.user_data.get('user_role')
    role_category = get_role_category(user_role) if user_role else None

    if role_category != 'CEO':
        await update.message.reply_text(
            GENERAL_TEXTS['survey_creation_permission']
        )
        return ConversationHandler.END

    await update.message.reply_text(SURVEY_TEXTS['create_welcome'])

    context.user_data['creating_survey'] = True
    return AWAITING_SURVEY_QUESTION


async def handle_survey_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на опрос"""
    # Проверяем, что пользователь действительно отвечает на опрос
    if not context.user_data.get('awaiting_survey_response'):
        # Если не в режиме ответа, игнорируем
        return

    if not context.user_data.get('current_survey_id'):
        await update.message.reply_text(
            "Ошибка: нет активного опроса для ответа. Используйте /response чтобы начать."
        )
        # Сбрасываем флаг
        context.user_data.pop('awaiting_survey_response', None)
        return ConversationHandler.END

    response_text = update.message.text.strip()

    if len(response_text) < 3:
        await update.message.reply_text(
            "Ответ должен содержать минимум 3 символа. Попробуйте снова:"
        )
        return AWAITING_SURVEY_RESPONSE

    # Получаем информацию об опросе
    survey_id = context.user_data['current_survey_id']
    question = context.user_data.get('current_survey_question', 'Без вопроса')
    survey_date = context.user_data.get('current_survey_datetime')

    # Сохраняем ответ в БД
    response_data = {
        'id_survey': survey_id,
        'id_user': context.user_data['user_id'],
        'answer': response_text
    }

    response_id = ResponseModel.save_response(response_data)

    if response_id:
        # Форматируем дату для сообщения
        date_str = ""
        if survey_date:
            if isinstance(survey_date, datetime):
                date_str = f"{survey_date.strftime('%d.%m.%Y %H:%M')}"
            elif isinstance(survey_date, str):
                date_str = survey_date
            else:
                date_str = str(survey_date)

        if date_str:
            await update.message.reply_text(
                f"Ваш ответ сохранен!\n\n"
                f"Опрос #{survey_id}\n"
                f"Вопрос: {question[:100]}...\n"
                f"Дата опроса: {date_str}"
            )
        else:
            await update.message.reply_text(
                f"Ваш ответ сохранен!\n\n"
                f"Опрос #{survey_id}\n"
                f"Вопрос: {question[:100]}..."
            )
    else:
        await update.message.reply_text(SURVEY_TEXTS['answer_error'])

    # Очищаем данные
    for key in ['current_survey_id', 'current_survey_question',
                'current_survey_datetime', 'awaiting_survey_response',
                'available_surveys', 'awaiting_survey_selection']:
        context.user_data.pop(key, None)

    return ConversationHandler.END


async def handle_survey_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка роли получателей"""
    role_input = update.message.text.strip().lower()
    # Определяем роль для БД
    if role_input == 'all':
        role_for_db = None  # В БД NULL означает "для всех"
        role_display = 'все пользователи'
    elif role_input == 'ceo':
        role_for_db = 'CEO'  # Всегда заглавными в БД
        role_display = 'руководители'
    else:
        # Для остальных ролей оставляем как есть (строчными)
        role_for_db = role_input
        # Формируем отображаемое имя
        role_display_map = {
            'worker': 'рабочие',
            'team_lead': 'тимлиды',
            'project_manager': 'менеджеры проектов',
            'department_head': 'руководители отделов',
            'senior_worker': 'старшие рабочие',
            'specialist': 'специалисты'
        }
        role_display = role_display_map.get(role_input, role_input)

    # Проверяем, есть ли пользователи с этой ролью (кроме 'all')
    if role_for_db:
        users = UserModel.get_users_by_role(role_for_db)
        if not users:
            await update.message.reply_text(
                SURVEY_TEXTS['no_users_for_role'].format(role=role_input)
            )
            return AWAITING_SURVEY_ROLE
        target_users_count = len(users)
    else:
        # Для 'all' считаем всех пользователей с Telegram
        users_worker = UserModel.get_users_by_role('worker')
        users_ceo = UserModel.get_users_by_role('CEO')
        target_users_count = len(users_worker) + len(users_ceo)

        if target_users_count == 0:
            await update.message.reply_text(SURVEY_TEXTS['no_users_registered'])
            return AWAITING_SURVEY_ROLE

    context.user_data['survey_role'] = role_for_db
    context.user_data['survey_role_display'] = role_display
    context.user_data['target_users_count'] = target_users_count

    await update.message.reply_text(
        SURVEY_TEXTS['role_saved'].format(
            count=target_users_count,
            role_display=role_display
        )
    )

    return AWAITING_SURVEY_TIME


async def handle_survey_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени отправки"""
    time_input = update.message.text.strip().lower()

    now = datetime.now()
    survey_datetime = None

    try:
        if time_input == 'сейчас':
            survey_datetime = now + timedelta(seconds=10)  # Через 10 секунд для теста
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
        'role': context.user_data['survey_role'],
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
            SURVEY_TEXTS['survey_created'].format(
                id=survey_id,
                question=context.user_data['survey_question'],
                role=role_display,
                count=users_count,
                time=schedule_time,
                type=schedule_type
            )
        )

        # Добавляем опрос в планировщик
        if hasattr(context, 'bot_data') and 'survey_scheduler' in context.bot_data:
            survey_scheduler = context.bot_data['survey_scheduler']

            # Всегда добавляем в планировщик, он сам решит когда отправлять
            await survey_scheduler.add_new_survey(survey_id, context.user_data['survey_datetime'])
        else:
            # Fallback
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Survey scheduler not available in bot_data for survey {survey_id}")

    else:
        await update.message.reply_text(SURVEY_TEXTS['survey_error'])

    # Очищаем данные
    for key in ['creating_survey', 'survey_question', 'survey_role',
                'survey_role_display', 'survey_datetime', 'target_users_count',
                'schedule_type']:
        context.user_data.pop(key, None)

    return ConversationHandler.END


async def send_survey_to_users(update: Update, context: ContextTypes.DEFAULT_TYPE, survey_id: int):
    """Отправка опроса пользователям"""
    await update.message.reply_text(
        SURVEY_TEXTS['survey_sent'].format(survey_id=survey_id)
    )


async def response_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ответа на опрос (доступна всем)"""
    user_id = context.user_data.get('user_id')
    user_role = context.user_data.get('user_role')

    # Опросы доступны всем авторизованным пользователям
    if not user_role:
        await update.message.reply_text(
            "Сначала авторизуйтесь с помощью /start"
        )
        return ConversationHandler.END

    # Получаем активные опросы для этой роли или для всех
    # 1. Опросы для конкретной роли пользователя
    active_surveys_for_role = SurveyModel.get_surveys_for_role(user_role)

    # 2. Опросы для всех (role = NULL)
    active_surveys_for_all = SurveyModel.get_surveys_for_role(None)

    # Объединяем опросы
    all_active_surveys = active_surveys_for_role + active_surveys_for_all

    if not all_active_surveys:
        await update.message.reply_text(SURVEY_TEXTS['no_active_surveys'])
        return

    # Фильтруем опросы, на которые пользователь еще не отвечал
    unanswered_surveys = []
    for survey in all_active_surveys:
        existing_response = ResponseModel.get_user_response(survey['id_survey'], user_id)
        if not existing_response:
            unanswered_surveys.append(survey)

    if not unanswered_surveys:
        await update.message.reply_text(SURVEY_TEXTS['all_surveys_answered'])
        return

    context.user_data['available_surveys'] = unanswered_surveys
    context.user_data['awaiting_survey_selection'] = True

    # Разбиваем список на части, если он слишком длинный
    chunks = []
    current_chunk = SURVEY_TEXTS['available_surveys_title']

    for i, survey in enumerate(unanswered_surveys, 1):
        # Определяем, для кого опрос
        target = survey['role'] if survey['role'] else "все пользователи"
        survey_text = (
            f"{i}. Опрос #{survey['id_survey']}\n"
            f"   Дата: {survey['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
            f"   Вопрос: {survey['question'][:80]}...\n"
            f"   Для: {target}\n\n"
        )

        # Если добавление нового элемента превысит лимит, начинаем новый чанк
        if len(current_chunk) + len(survey_text) > 4000:
            chunks.append(current_chunk)
            current_chunk = f"Доступные опросы (продолжение):\n\n{survey_text}"
        else:
            current_chunk += survey_text

    # Добавляем последний чанк с инструкцией
    if current_chunk:
        chunks.append(current_chunk + SURVEY_TEXTS['select_survey_prompt'])

    # Отправляем первый чанк
    if chunks:
        await update.message.reply_text(chunks[0])

        # Остальные чанки отправляем с задержкой
        for chunk in chunks[1:]:
            await asyncio.sleep(0.5)
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(SURVEY_TEXTS['no_active_surveys'])

    return AWAITING_SURVEY_SELECTION


async def handle_survey_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора опроса"""
    selection_text = update.message.text.strip()

    try:
        selection_num = int(selection_text)
    except ValueError:
        await update.message.reply_text(
            SURVEY_TEXTS['invalid_survey_number']
        )
        return AWAITING_SURVEY_SELECTION

    available_surveys = context.user_data.get('available_surveys', [])

    if not 1 <= selection_num <= len(available_surveys):
        await update.message.reply_text(
            SURVEY_TEXTS['survey_out_of_range'].format(count=len(available_surveys))
        )
        return AWAITING_SURVEY_SELECTION

    selected_survey = available_surveys[selection_num - 1]

    context.user_data['current_survey_id'] = selected_survey['id_survey']
    context.user_data['current_survey_question'] = selected_survey['question']
    context.user_data['current_survey_datetime'] = selected_survey['datetime']
    context.user_data['awaiting_survey_response'] = True

    # Инициализируем пустой ответ для собирания по частям
    context.user_data['response_parts'] = []

    context.user_data.pop('available_surveys', None)
    context.user_data.pop('awaiting_survey_selection', None)

    # Определяем, для кого опрос
    target = selected_survey['role'] if selected_survey['role'] else "все пользователи"

    # ЧИСТЫЙ ТЕКСТ БЕЗ ЛИШНЕЙ ИНФОРМАЦИИ
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
                'response_parts', 'available_surveys', 'awaiting_survey_selection']:
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


survey_response_conversation = ConversationHandler(
    entry_points=[CommandHandler('response', response_command)],
    states={
        AWAITING_SURVEY_SELECTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_survey_selection)
        ],
        AWAITING_SURVEY_RESPONSE_PART: [  # Измененное состояние
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response_part)
        ],
    },
    fallbacks=[
        CommandHandler('done', finish_response_command),  # Новая команда завершения
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
        AWAITING_SURVEY_ROLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_survey_role)
        ],
        AWAITING_SURVEY_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_survey_time)
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel_survey)],
)
