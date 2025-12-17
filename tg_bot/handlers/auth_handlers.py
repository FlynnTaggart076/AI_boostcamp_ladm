import logging

from telegram import Update
from telegram.ext import ConversationHandler, ContextTypes

from tg_bot.config.constants import AWAITING_PASSWORD, AWAITING_NAME, AWAITING_JIRA, AWAITING_ROLE
from tg_bot.config.settings import config
from tg_bot.config.texts import (
    REGISTRATION_TEXTS, AUTH_TEXTS, get_role_display_name
)
from tg_bot.database.models import UserModel
from tg_bot.services.user_service import user_service
from tg_bot.services.validators import Validator
from tg_bot.handlers.role_handlers import show_role_selection

logger = logging.getLogger(__name__)


def _cleanup_registration_data(context):
    """Очистка данных регистрации из context"""
    keys_to_remove = [
        'awaiting_password', 'awaiting_name', 'awaiting_jira', 'awaiting_role',
        'user_name', 'jira_account', 'existing_jira_user', 'existing_user_id',
        'target_users_count', 'survey_role_display', 'selected_category', 'selected_role'
    ]

    for key in keys_to_remove:
        context.user_data.pop(key, None)


async def handle_message(update, context):
    """Обработка текстовых сообщений - УЛУЧШЕННАЯ ВЕРСИЯ"""
    # Сначала проверяем, находится ли пользователь в процессе создания опроса
    if context.user_data.get('creating_survey'):
        from tg_bot.handlers.survey_handlers import AWAITING_SURVEY_TIME, handle_survey_time
        # Если пользователь в процессе создания опроса и ожидает ввода времени
        if 'survey_question' in context.user_data and 'survey_role' in context.user_data:
            # Это ввод времени для опроса
            return await handle_survey_time(update, context)

    # Если пользователь в процессе регистрации
    if context.user_data.get('awaiting_password'):
        # Проверка пароля
        if update.message.text == config.REGISTRATION_PASSWORD:
            context.user_data['awaiting_password'] = False
            context.user_data['awaiting_name'] = True

            await update.message.reply_text(REGISTRATION_TEXTS['password_correct'])
            return AWAITING_NAME
        else:
            await update.message.reply_text(REGISTRATION_TEXTS['password_wrong'])
            return AWAITING_PASSWORD

    elif context.user_data.get('awaiting_name'):
        # Валидация имени
        name = update.message.text.strip()
        is_valid, error_msg = Validator.validate_user_name(name)

        if not is_valid:
            await update.message.reply_text(f"{error_msg}. Попробуйте снова:")
            return AWAITING_NAME

        context.user_data['awaiting_name'] = False
        context.user_data['awaiting_jira'] = True
        context.user_data['user_name'] = name

        await update.message.reply_text(REGISTRATION_TEXTS['name_saved'])
        return AWAITING_JIRA

    elif context.user_data.get('awaiting_jira'):
        """Обработка ввода Jira аккаунта - ПРОСТАЯ ВЕРСИЯ"""
        jira_input = update.message.text.strip()

        # Проверяем, не хочет ли пользователь пропустить
        skip_keywords = ['нет', 'н', 'no', 'n', 'skip', 'пропустить']

        if jira_input.lower() in skip_keywords:
            jira_account = None
            await update.message.reply_text("Jira аккаунт не указан. Продолжаем регистрацию...")
        else:
            jira_account = jira_input
            await update.message.reply_text(f"Jira аккаунт сохранен: {jira_account}")

        context.user_data['awaiting_jira'] = False
        context.user_data['jira_account'] = jira_account

        # Показываем выбор роли через кнопки
        return await show_role_selection(update, context)

    # Если пользователь авторизован и отвечает на опрос
    elif context.user_data.get('awaiting_survey_response'):
        from tg_bot.handlers.survey_handlers import handle_response_part
        return await handle_response_part(update, context)
    elif context.user_data.get('awaiting_add_response_part'):
        from tg_bot.handlers.addresponse_handlers import handle_add_response_part
        return await handle_add_response_part(update, context)
    else:
        # Пользователь авторизован, но отправил неизвестную команду
        await update.message.reply_text(AUTH_TEXTS['unknown_command'])


async def complete_registration_with_role(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_role: str):
    """Завершение регистрации с выбранной ролью"""
    # Получаем Telegram данные
    user = update.effective_user
    telegram_username = user.username or str(user.id)
    tg_id = user.id
    user_name = context.user_data['user_name']
    jira_account = context.user_data['jira_account']

    # Используем UserService для регистрации
    result = user_service.register_or_update_user(
        name=user_name,
        telegram_username=telegram_username,
        tg_id=tg_id,
        role=selected_role,
        jira_account=jira_account
    )

    if result['success']:
        # Сохраняем контекст пользователя
        user_context = user_service.get_user_context(telegram_username)
        context.user_data.update(user_context)

        # Формируем сообщение
        role_display = get_role_display_name(selected_role)
        jira_info = f"Jira: {jira_account}" if jira_account else "Jira: не указан"

        await update.callback_query.edit_message_text(
            f"{result['message']}!\n\n"
            f"Имя: {user_name}\n"
            f"Роль: {role_display}\n"
            f"Telegram: @{telegram_username}\n"
            f"{jira_info}\n\n"
            f"Используйте /help для списка команд."
        )

        try:
            from tg_bot.handlers.menu_handlers import update_user_commands
            await update_user_commands(update, context)
        except Exception as e:
            logger.error(f"Ошибка обновления команд: {e}")
    else:
        await update.callback_query.edit_message_text(
            f"{result['message']}\n"
            f"Обратитесь к администратору."
        )

    # Очищаем данные регистрации
    _cleanup_registration_data(context)
    return ConversationHandler.END


async def start_command(update, context):
    """Обработчик команды /start"""
    user = update.effective_user
    telegram_username = user.username or str(user.id)

    # Проверяем, авторизован ли пользователь
    user_data = UserModel.get_user_by_telegram_username(telegram_username)

    if user_data:
        # Пользователь уже авторизован
        role_display = get_role_display_name(user_data['role'])
        jira_info = "📋 Jira: не указан"
        if user_data.get('jira_name'):
            jira_info = f"Jira: {user_data['jira_name']}"
        elif user_data.get('jira_email'):
            jira_info = f"Jira: {user_data['jira_email']}"

        response_text = REGISTRATION_TEXTS['already_registered'].format(
            name=user_data['user_name'],
            role=role_display,
            jira_info=jira_info
        )

        context.user_data['user_role'] = user_data['role']
        context.user_data['user_id'] = user_data['id_user']
        context.user_data['user_name'] = user_data['user_name']
        context.user_data['jira_account'] = user_data.get('jira_name') or user_data.get('jira_email')

        # Проверяем, вызвана ли команда из меню
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)

        # Обновляем команды
        try:
            from tg_bot.handlers.menu_handlers import update_user_commands
            await update_user_commands(update, context)
        except Exception as e:
            logger.error(f"Ошибка обновления команд: {e}")

        return ConversationHandler.END
    else:
        # Начинаем процесс регистрации
        response_text = REGISTRATION_TEXTS['welcome']

        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(response_text)
            # Сохраняем информацию о сообщении меню
            context.user_data['menu_start_message_id'] = update.callback_query.message.message_id
        else:
            await update.message.reply_text(response_text)

        context.user_data['awaiting_password'] = True
        return AWAITING_PASSWORD
