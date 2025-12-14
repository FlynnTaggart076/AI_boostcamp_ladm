from telegram import Update
from telegram.ext import ContextTypes
from tg_bot.database.models import BlockerModel, DailyDigestModel, WeekDigestModel
from datetime import datetime, timedelta
from tg_bot.config.validators import validate_date


async def dailydigest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /dailydigest"""
    user_role = context.user_data.get('user_role')

    # Определяем дату отчета
    date_str = None
    if context.args:
        date_str = context.args[0]
        if not validate_date(date_str):
            await update.message.reply_text(
                "Неверный формат даты. Используйте ГГГГ-ММ-ДД\n"
                "Пример: /dailydigest 2024-01-15"
            )
            return
    else:
        # По умолчанию - вчерашний день
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')

    # Получаем ежедневный дайджест
    digests = DailyDigestModel.get_daily_digest(date_str)

    if not digests:
        await update.message.reply_text(
            f"Ежедневный дайджест за {date_str}\n\n"
            f"Нет данных за указанную дату."
        )
        return

    # Формируем ответ
    response = f"Ежедневный дайджест за {date_str}\n\n"

    for digest in digests:
        response += f"{digest['text']}\n\n"

    await update.message.reply_text(response)


async def weeklydigest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /weeklydigest"""

    if context.args and len(context.args) >= 2:
        start_date = context.args[0]
        end_date = context.args[1]

        if not validate_date(start_date) or not validate_date(end_date):
            await update.message.reply_text(
                "Неверный формат даты. Используйте ГГГГ-ММ-ДД\n"
                "Пример: /weeklydigest 2024-01-08 2024-01-14"
            )
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
        await update.message.reply_text(
            f"Еженедельный дайджест с {start_date} по {end_date}\n\n"
            f"Нет данных за указанный период."
        )
        return

    response = f"Еженедельный дайджест с {start_date} по {end_date}\n\n"

    for digest in digests:
        date = digest['datetime'].strftime('%d.%m.%Y') if isinstance(digest['datetime'], datetime) else digest[
            'datetime']
        response += f"{date}:\n"
        response += f"{digest['text']}\n\n"

    await update.message.reply_text(response)


async def blockers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /blockers"""
    user_role = context.user_data.get('user_role')

    date_str = None
    if context.args:
        date_str = context.args[0]
        if not validate_date(date_str):
            await update.message.reply_text(
                "Неверный формат даты. Используйте ГГГГ-ММ-ДД"
            )
            return
    else:
        date_str = datetime.now().strftime('%Y-%m-%d')

    # Получаем блокеры за дату
    blockers = BlockerModel.get_blockers_by_date(date_str)

    if not blockers:
        await update.message.reply_text(
            f"Блокеры за {date_str}\n\n"
            f"Нет данных о блокерах за указанную дату."
        )
        return

    response = f"Блокеры за {date_str}\n\n"

    critical_count = 0
    regular_count = 0

    for blocker in blockers:
        if blocker.get('critical'):
            critical_count += 1
            response += f"КРИТИЧЕСКИЙ:\n"
        else:
            regular_count += 1
            response += f"Обычный:\n"

        response += f"{blocker.get('user_name', 'Неизвестный')}\n"
        response += f"{blocker['text']}\n"

        if blocker.get('response'):
            response += f"Ответ: {blocker['response']}\n"

        response += f"Исходный ответ: {blocker.get('answer', 'нет')[:100]}...\n\n"

    response += f"Итого: {len(blockers)} блокеров ({critical_count} критических, {regular_count} обычных)"

    await update.message.reply_text(response)