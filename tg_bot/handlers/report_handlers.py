from telegram import Update
from telegram.ext import ContextTypes
from tg_bot.database.models import BlockerModel, DailyDigestModel, WeekDigestModel
from datetime import datetime, timedelta
from tg_bot.config.validators import validate_date


async def dailydigest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.args:
        date_str = context.args[0]
    else:
        # По умолчанию - вчерашний день
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')

    # Получаем ежедневный дайджест
    digests = DailyDigestModel.get_daily_digest(date_str)

    if not digests:
        response_text = f"Ежедневный дайджест за {date_str}\n\nНет данных за указанную дату."
    else:
        # Формируем ответ
        response_text = f"Ежедневный дайджест за {date_str}\n\n"
        for digest in digests:
            response_text += f"{digest['text']}\n\n"

    # Проверяем, вызвана ли команда из меню
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(response_text)
    else:
        await update.message.reply_text(response_text)


async def weeklydigest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /weeklydigest"""
    if context.args and len(context.args) >= 2:
        start_date = context.args[0]
        end_date = context.args[1]

        if not validate_date(start_date) or not validate_date(end_date):
            response_text = (
                "Неверный формат даты. Используйте ГГГГ-ММ-ДД\n"
                "Пример: /weeklydigest 2024-01-08 2024-01-14"
            )
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(response_text)
            else:
                await update.message.reply_text(response_text)
            return
    else:
        # По умолчанию - прошлая неделя
        end_date = datetime.now() - timedelta(days=datetime.now().weekday() + 1)
        start_date = end_date - timedelta(days=6)
        start_date = start_date.strftime('%Y-%m-%d')
        end_date = end_date.strftime('%Y-%m-%d')

    # Получаем еженедельные дайджесты
    digests = WeekDigestModel.get_week_digest(start_date, end_date)

    if not digests:
        response_text = f"Еженедельный дайджест с {start_date} по {end_date}\n\nНет данных за указанный период."
    else:
        response_text = f"Еженедельный дайджест с {start_date} по {end_date}\n\n"
        for digest in digests:
            date = digest['datetime'].strftime('%d.%m.%Y') if isinstance(digest['datetime'], datetime) \
                else digest['datetime']
            response_text += f"{date}:\n"
            response_text += f"{digest['text']}\n\n"

    # Проверяем, вызвана ли команда из меню
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(response_text)
    else:
        await update.message.reply_text(response_text)


async def blockers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.args:
        date_str = context.args[0]
        if not validate_date(date_str):
            response_text = "Неверный формат даты. Используйте ГГГГ-ММ-ДД"
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(response_text)
            else:
                await update.message.reply_text(response_text)
            return
    else:
        date_str = datetime.now().strftime('%Y-%m-%d')

    blockers = BlockerModel.get_blockers_by_date(date_str)

    if not blockers:
        response_text = f"Блокеры за {date_str}\n\nНет данных о блокерах за указанную дату."
    else:
        response_text = f"Блокеры за {date_str}\n\n"
        critical_count = 0
        regular_count = 0

        for blocker in blockers:
            if blocker.get('critical'):
                critical_count += 1
                response_text += f"КРИТИЧЕСКИЙ:\n"
            else:
                regular_count += 1
                response_text += f"Обычный:\n"

            response_text += f"{blocker.get('user_name', 'Неизвестный')}\n"
            response_text += f"{blocker['text']}\n"

            if blocker.get('response'):
                response_text += f"Ответ: {blocker['response']}\n"

            response_text += f"Исходный ответ: {blocker.get('answer', 'нет')[:100]}...\n\n"

        response_text += f"Итого: {len(blockers)} блокеров ({critical_count} критических, {regular_count} обычных)"

    # Проверяем, вызвана ли команда из меню
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(response_text)
    else:
        await update.message.reply_text(response_text)
