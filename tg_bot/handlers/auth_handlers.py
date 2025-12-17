from telegram.ext import ConversationHandler
import logging
from tg_bot.config.constants import AWAITING_PASSWORD, AWAITING_ROLE, AWAITING_JIRA, AWAITING_NAME, \
    REGISTRATION_PASSWORD
from tg_bot.config.settings import config
from tg_bot.database.models import UserModel
from tg_bot.handlers.survey_handlers import handle_survey_response
from tg_bot.services.jira_handler import process_jira_registration
from tg_bot.config.texts import (
    REGISTRATION_TEXTS, AUTH_TEXTS, ROLE_DISPLAY,
    get_role_display_name, format_registration_complete
)
from tg_bot.services.user_service import user_service
from tg_bot.services.validators import Validator

logger = logging.getLogger(__name__)


def _cleanup_registration_data(context):
    """Очистка данных регистрации из context"""
    keys_to_remove = [
        'awaiting_password', 'awaiting_name', 'awaiting_jira', 'awaiting_role',
        'user_name', 'jira_account', 'existing_jira_user', 'existing_user_id',
        'target_users_count', 'survey_role_display'
    ]

    for key in keys_to_remove:
        context.user_data.pop(key, None)


async def handle_message(update, context):
    """Обработка текстовых сообщений"""
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
            await update.message.reply_text(f"❌ {error_msg}. Попробуйте снова:")
            return AWAITING_NAME

        context.user_data['awaiting_name'] = False
        context.user_data['awaiting_jira'] = True
        context.user_data['user_name'] = name

        await update.message.reply_text(REGISTRATION_TEXTS['name_saved'])
        return AWAITING_JIRA

    elif context.user_data.get('awaiting_jira'):
        # Валидация Jira аккаунта
        jira_account = update.message.text.strip()

        # Если пользователь ввел "нет" или пустую строку
        if jira_account.lower() in ['нет', 'н', 'no', 'n', 'skip', 'пропустить', '']:
            jira_account = None
        else:
            # Валидация Jira аккаунта
            is_valid, error_msg = Validator.validate_jira_account(jira_account)
            if not is_valid:
                await update.message.reply_text(f"❌ {error_msg}. Попробуйте снова:")
                return AWAITING_JIRA

        context.user_data['awaiting_jira'] = False
        context.user_data['awaiting_role'] = True
        context.user_data['jira_account'] = jira_account

        # НОВАЯ ЛОГИКА: Используем UserService
        if jira_account:
            jira_user = user_service.find_user_by_jira_account(jira_account)

            if jira_user:
                context.user_data['existing_jira_user'] = jira_user
                context.user_data['existing_user_id'] = jira_user['id_user']

                if jira_user.get('tg_username'):
                    await update.message.reply_text(
                        f"⚠️  Пользователь с Jira аккаунтом '{jira_account}' уже зарегистрирован.\n"
                        f"Или выберите роль для продолжения регистрации:"
                    )
                else:
                    await update.message.reply_text(
                        f"✅ Найден пользователь Jira: {jira_user.get('jira_name', jira_account)}\n"
                        f"Теперь выберите вашу роль:\n\n" + REGISTRATION_TEXTS['role_options']
                    )
            else:
                await update.message.reply_text(
                    f"ℹ️  Пользователь с Jira аккаунтом '{jira_account}' не найден.\n"
                    f"Будет создан новый профиль.\n\n" + REGISTRATION_TEXTS['role_options']
                )
        else:
            await update.message.reply_text(
                "ℹ️  Jira аккаунт не указан. Будет создан новый профиль.\n\n" +
                REGISTRATION_TEXTS['role_options']
            )

        return AWAITING_ROLE

    elif context.user_data.get('awaiting_role'):
        # Валидация и нормализация роли
        role_input = update.message.text.strip()
        is_valid, error_msg, normalized_role = Validator.validate_role(role_input)

        if not is_valid:
            await update.message.reply_text(f"❌ {error_msg}")
            return AWAITING_ROLE

        # Получаем Telegram данные
        user = update.effective_user
        telegram_username = user.username or str(user.id)
        tg_id = user.id
        user_name = context.user_data['user_name']
        jira_account = context.user_data['jira_account']

        # НОВАЯ ЛОГИКА: Используем UserService для регистрации
        result = user_service.register_or_update_user(
            name=user_name,
            telegram_username=telegram_username,
            tg_id=tg_id,
            role=normalized_role,
            jira_account=jira_account
        )

        if result['success']:
            # Сохраняем контекст пользователя
            user_context = user_service.get_user_context(telegram_username)
            context.user_data.update(user_context)

            # Формируем сообщение
            role_display = get_role_display_name(normalized_role)
            jira_info = f"Jira: {jira_account}" if jira_account else "Jira: не указан"

            await update.message.reply_text(
                f"✅ {result['message']}!\n\n"
                f"👤 Имя: {user_name}\n"
                f"👔 Роль: {role_display}\n"
                f"📱 Telegram: @{telegram_username}\n"
                f"{jira_info}\n\n"
                f"Используйте /help для списка команд."
            )

            try:
                from tg_bot.handlers.menu_handlers import update_user_commands
                await update_user_commands(update, context)
            except Exception as e:
                logger.error(f"Ошибка обновления команд: {e}")
        else:
            await update.message.reply_text(
                f"❌ {result['message']}\n"
                f"Обратитесь к администратору."
            )

        # Очищаем данные регистрации
        _cleanup_registration_data(context)
        return ConversationHandler.END

    # Если пользователь авторизован и отвечает на опрос
    elif context.user_data.get('awaiting_survey_response'):
        return await handle_survey_response(update, context)

    else:
        # Пользователь авторизован, но отправил неизвестную команду
        await update.message.reply_text(AUTH_TEXTS['unknown_command'])


async def start_command(update, context):
    """Обработчик команды /start"""
    user = update.effective_user
    telegram_username = user.username or str(user.id)

    # Проверяем, авторизован ли пользователь
    user_data = UserModel.get_user_by_telegram_username(telegram_username)

    if user_data:
        # Пользователь уже авторизован
        role_display = get_role_display_name(user_data['role'])

        # Формируем информацию о Jira
        jira_info = "📋 Jira: не указан"
        if user_data.get('jira_name'):
            jira_info = f"Jira: {user_data['jira_name']}"
        elif user_data.get('jira_email'):
            jira_info = f"Jira: {user_data['jira_email']}"

        await update.message.reply_text(
            REGISTRATION_TEXTS['already_registered'].format(
                name=user_data['user_name'],
                role=role_display,
                jira_info=jira_info
            )
        )

        context.user_data['user_role'] = user_data['role']
        context.user_data['user_id'] = user_data['id_user']
        context.user_data['user_name'] = user_data['user_name']
        context.user_data['jira_account'] = user_data.get('jira_name') or user_data.get('jira_email')

        # ВАЖНО: Обновляем команды для этого пользователя
        try:
            from tg_bot.handlers.menu_handlers import update_user_commands
            await update_user_commands(update, context)
        except Exception as e:
            logger.error(f"Ошибка обновления команд: {e}")

        return ConversationHandler.END
    else:
        # Начинаем процесс регистрации
        await update.message.reply_text(REGISTRATION_TEXTS['welcome'])

        context.user_data['awaiting_password'] = True
        return AWAITING_PASSWORD