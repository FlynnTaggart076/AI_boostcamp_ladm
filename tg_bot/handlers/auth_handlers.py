from telegram.ext import ConversationHandler
import logging
from tg_bot.config.constants import AWAITING_PASSWORD, AWAITING_ROLE, AWAITING_JIRA, AWAITING_NAME, \
    REGISTRATION_PASSWORD
from tg_bot.database.models import UserModel
from tg_bot.handlers.survey_handlers import handle_survey_response
from tg_bot.services.jira_handler import process_jira_registration
from tg_bot.config.texts import (
    REGISTRATION_TEXTS, AUTH_TEXTS, ROLE_DISPLAY,
    get_role_display_name, format_registration_complete
)

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
        if update.message.text == REGISTRATION_PASSWORD:
            context.user_data['awaiting_password'] = False
            context.user_data['awaiting_name'] = True

            await update.message.reply_text(REGISTRATION_TEXTS['password_correct'])
            return AWAITING_NAME
        else:
            await update.message.reply_text(REGISTRATION_TEXTS['password_wrong'])
            return AWAITING_PASSWORD

    elif context.user_data.get('awaiting_name'):
        # Сохраняем имя и запрашиваем Jira аккаунт
        name = update.message.text.strip()

        if len(name) < 2:
            await update.message.reply_text(
                "❌ Имя должно содержать минимум 2 символа. Попробуйте снова:"
            )
            return AWAITING_NAME

        context.user_data['awaiting_name'] = False
        context.user_data['awaiting_jira'] = True
        context.user_data['user_name'] = name

        await update.message.reply_text(REGISTRATION_TEXTS['name_saved'])
        return AWAITING_JIRA

    elif context.user_data.get('awaiting_jira'):
        # Сохраняем Jira аккаунт и запрашиваем роль
        jira_account = update.message.text.strip()

        # Если пользователь ввел "нет" или пустую строку, сохраняем None
        if jira_account.lower() in ['нет', 'н', 'no', 'n', 'skip', 'пропустить', '']:
            jira_account = None

        context.user_data['awaiting_jira'] = False
        context.user_data['awaiting_role'] = True
        context.user_data['jira_account'] = jira_account

        # НОВАЯ ЛОГИКА: Проверяем, есть ли такой пользователь уже в Jira
        existing_jira_user = None
        if jira_account:
            # Пытаемся найти по имени Jira
            existing_jira_user = UserModel.get_user_by_jira_name(jira_account)

            # Если не нашли по имени, пробуем найти по email
            if not existing_jira_user and '@' in jira_account:
                existing_jira_user = UserModel.get_user_by_jira_email(jira_account)

        # Сохраняем информацию о найденном пользователе
        if existing_jira_user:
            context.user_data['existing_jira_user'] = existing_jira_user
            context.user_data['existing_user_id'] = existing_jira_user['id_user']

            # Если у пользователя уже есть Telegram данные, сообщаем
            if existing_jira_user.get('tg_username'):
                await update.message.reply_text(
                    f"⚠️  Пользователь с Jira аккаунтом '{jira_account}' уже зарегистрирован в Telegram.\n"
                    f"Если это вы, используйте /start с тем же Telegram аккаунтом.\n"
                    f"Если это не вы, введите другой Jira аккаунт.\n\n"
                    "Или выберите роль для продолжения регистрации:"
                )
            else:
                await update.message.reply_text(
                    f"✅ Найден пользователь Jira: {existing_jira_user.get('jira_name', jira_account)}\n"
                    f"Теперь выберите вашу роль в системе:\n\n" + REGISTRATION_TEXTS['role_options']
                )
        else:
            if jira_account:
                await update.message.reply_text(
                    f"ℹ️  Пользователь с Jira аккаунтом '{jira_account}' не найден в системе.\n"
                    f"Будет создан новый профиль.\n\n" + REGISTRATION_TEXTS['role_options']
                )
            else:
                await update.message.reply_text(
                    "ℹ️  Jira аккаунт не указан. Будет создан новый профиль.\n\n" +
                    REGISTRATION_TEXTS['role_options']
                )

        return AWAITING_ROLE

    elif context.user_data.get('awaiting_role'):
        # Сохраняем роль и регистрируем пользователя
        role_input = update.message.text.strip().lower()

        # Проверяем и нормализуем ввод
        role_map = {
            'ceo': 'CEO',
            'worker': 'worker',
            'team_lead': 'team_lead',
            'team lead': 'team_lead',
            'project_manager': 'project_manager',
            'project manager': 'project_manager',
            'department_head': 'department_head',
            'department head': 'department_head',
            'senior_worker': 'senior_worker',
            'senior worker': 'senior_worker',
            'specialist': 'specialist'
        }

        role = role_map.get(role_input, role_input)

        # Проверяем, что роль валидная
        valid_roles = ['CEO', 'worker', 'team_lead', 'project_manager',
                       'department_head', 'senior_worker', 'specialist']

        if role not in valid_roles:
            await update.message.reply_text(REGISTRATION_TEXTS['invalid_role'])
            return AWAITING_ROLE

        # Получаем Telegram данные
        user = update.effective_user
        telegram_username = user.username or str(user.id)
        tg_id = user.id
        user_name = context.user_data['user_name']
        jira_account = context.user_data['jira_account']

        # НОВАЯ ЛОГИКА: Проверяем, есть ли уже такой пользователь в Telegram
        existing_telegram_user = UserModel.get_user_by_telegram_username(telegram_username)

        if existing_telegram_user:
            # Пользователь уже зарегистрирован в Telegram
            await update.message.reply_text(
                REGISTRATION_TEXTS['already_registered'].format(
                    name=existing_telegram_user['name'],
                    role=get_role_display_name(existing_telegram_user['role']),
                    jira_info=f"Jira: {existing_telegram_user.get('jira_name', 'не указан')}"
                )
            )

            # Сохраняем данные в context
            context.user_data['user_role'] = existing_telegram_user['role']
            context.user_data['user_id'] = existing_telegram_user['id_user']
            context.user_data['user_name'] = existing_telegram_user['name']
            context.user_data['jira_account'] = existing_telegram_user.get('jira_name')

            # Очищаем данные регистрации
            _cleanup_registration_data(context)
            return ConversationHandler.END

        # ЛОГИКА РЕГИСТРАЦИИ НОВОГО ПОЛЬЗОВАТЕЛЯ
        registration_success = False
        existing_jira_user = context.user_data.get('existing_jira_user')

        if existing_jira_user:
            # СЛУЧАЙ 1: Пользователь найден в Jira - обновляем его данные
            logger.info(f"Обновление существующего пользователя Jira: {existing_jira_user['id_user']}")

            # Обновляем существующего пользователя Jira
            success = UserModel.update_existing_jira_user(
                user_id=existing_jira_user['id_user'],
                telegram_username=telegram_username,
                tg_id=tg_id,
                role=role,
                name=user_name
            )

            if success:
                registration_success = True
                registered_user = existing_jira_user.copy()
                registered_user.update({
                    'tg_username': telegram_username,
                    'tg_id': tg_id,
                    'role': role,
                    'name': user_name
                })
                logger.info(f"✅ Существующий пользователь Jira обновлен: {user_name}")
            else:
                await update.message.reply_text(
                    "❌ Ошибка обновления пользователя Jira.\n"
                    "Попробуйте снова или обратитесь к администратору."
                )
                _cleanup_registration_data(context)
                return ConversationHandler.END

        else:
            # СЛУЧАЙ 2: Новый пользователь - создаём запись
            logger.info(f"Создание нового пользователя: {user_name}")

            # Определяем jira_name и jira_email из jira_account
            jira_name = None
            jira_email = None

            if jira_account:
                if '@' in jira_account:
                    jira_email = jira_account
                    jira_name = jira_account.split('@')[0]
                else:
                    jira_name = jira_account

            # Создаем новую запись пользователя
            success = UserModel.register_user(
                name=user_name,
                telegram_username=telegram_username,
                tg_id=tg_id,
                role=role,
                jira_account=jira_account
            )

            if success:
                registration_success = True
                # Получаем созданного пользователя
                registered_user = UserModel.get_user_by_telegram_username(telegram_username)
                logger.info(f"✅ Новый пользователь создан: {user_name}")
            else:
                await update.message.reply_text(
                    "❌ Ошибка регистрации пользователя.\n"
                    "Возможные причины:\n"
                    "1. Пользователь с таким Telegram уже зарегистрирован\n"
                    "2. Проблема с подключением к базе данных\n\n"
                    "Обратитесь к администратору."
                )
                _cleanup_registration_data(context)
                return ConversationHandler.END

        # После успешной регистрации
        if registration_success and registered_user:
            # Проверяем Jira аккаунт (только для информации)
            if jira_account:
                try:
                    jira_success = await process_jira_registration(
                        user_id=registered_user['id_user'],
                        jira_account=jira_account,
                        user_name=user_name
                    )

                    if not jira_success:
                        logger.warning(f"Не удалось проверить Jira аккаунт: {jira_account}")
                except Exception as e:
                    logger.error(f"Ошибка проверки Jira при регистрации: {e}")
                    # Не прерываем регистрацию из-за ошибки Jira

            # Сохраняем данные в context
            context.user_data['user_role'] = role
            context.user_data['user_id'] = registered_user['id_user']
            context.user_data['user_name'] = user_name
            context.user_data['jira_account'] = jira_account

            # Показываем успешную регистрацию
            role_display = get_role_display_name(role)
            jira_info = f"Jira: {jira_account}" if jira_account else "Jira: не указан"

            await update.message.reply_text(
                f"✅ Регистрация завершена успешно!\n\n"
                f"👤 Имя: {user_name}\n"
                f"👔 Роль: {role_display}\n"
                f"📱 Telegram: @{telegram_username}\n"
                f"{jira_info}\n\n"
                f"Используйте /help для списка команд."
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
                name=user_data['name'],
                role=role_display,
                jira_info=jira_info
            )
        )

        # Сохраняем данные в context
        context.user_data['user_role'] = user_data['role']
        context.user_data['user_id'] = user_data['id_user']
        context.user_data['user_name'] = user_data['name']
        context.user_data['jira_account'] = user_data.get('jira_name') or user_data.get('jira_email')

        return ConversationHandler.END
    else:
        # Начинаем процесс регистрации
        await update.message.reply_text(REGISTRATION_TEXTS['welcome'])

        context.user_data['awaiting_password'] = True
        return AWAITING_PASSWORD