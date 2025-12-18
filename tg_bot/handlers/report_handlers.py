# report_handlers.py - НОВЫЙ ФАЙЛ
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from tg_bot.config.texts import REPORT_TEXTS

logger = logging.getLogger(__name__)


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /report - показывает сообщение о перенаправлении"""

    # Формируем сообщение
    response_text = REPORT_TEXTS['report_message']

    # Проверяем, вызвана ли команда из меню
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(response_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(response_text, parse_mode='Markdown')


async def report_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия кнопки отчетов в меню"""
    query = update.callback_query
    await query.answer()

    # Показываем то же сообщение что и для команды /report
    response_text = REPORT_TEXTS['report_message']
    await query.edit_message_text(response_text, parse_mode='Markdown')


def setup_report_handlers(application):
    """Настройка обработчиков отчетов"""
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("dailydigest", report_command))  # Перенаправляем старые команды
    application.add_handler(CommandHandler("weeklydigest", report_command))
    application.add_handler(CommandHandler("blockers", report_command))
    logger.info("Обработчики отчетов настроены")