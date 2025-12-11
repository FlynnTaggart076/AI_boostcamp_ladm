from telegram.ext import ConversationHandler
import logging
from config.constants import AWAITING_PASSWORD, AWAITING_ROLE, AWAITING_JIRA, AWAITING_NAME, REGISTRATION_PASSWORD
from database.models import UserModel
from services.jira_handler import process_jira_registration

logger = logging.getLogger(__name__)


async def handle_message(update, context):
    """Обработка текстовых сообщений"""
    # Если пользователь в процессе регистрации
    if context.user_data.get('awaiting_password'):
        # Проверка пароля
        if update.message.text == REGISTRATION_PASSWORD:
            context.user_data['awaiting_password'] = False
            context.user_data['awaiting_name'] = True

            await update.message.reply_text(
                "✅ Пароль верный!\n\n"
                "Теперь введите ваше полное имя (ФИО):\n"
                "Пример: Иванов Иван Иванович\n\n"
                "Используйте /cancel для отмены."
            )
            return AWAITING_NAME
        else:
            await update.message.reply_text(
                "❌ Неверный пароль. Попробуйте снова или используйте /cancel:"
            )
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

        await update.message.reply_text(
            "👤 Имя сохранено!\n\n"
            "Теперь введите ваш Jira аккаунт (email или логин):\n"
            "Пример: ivan.ivanov@company.com\n"
            "Или: iivanov\n\n"
            "Если у вас нет Jira аккаунта, введите 'нет' или пропустите."
        )
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

        await update.message.reply_text(
            "📋 Jira account saved!\n\n"
            "Choose your role:\n"
            "Available roles (English only):\n"
            "• worker - basic worker\n"
            "• CEO - manager (can create surveys)\n"
            "• team_lead - team leader\n"
            "• project_manager - project manager\n"
            "• department_head - department head\n"
            "• senior_worker - senior worker\n"
            "• specialist - specialist\n\n"
            "Enter role name:"
        )
        return AWAITING_ROLE


    elif context.user_data.get('awaiting_role'):
        # Сохраняем роль и регистрируем пользователя
        role_input = update.message.text.strip().lower()

        # Проверяем и нормализуем ввод
        if role_input == 'CEO' or role_input == 'ceo':
            role = 'CEO'
        elif role_input == 'worker':
            role = 'worker'
        elif role_input in ['team_lead', 'project_manager', 'department_head', 'senior_worker', 'specialist']:
            role = role_input
        elif role_input == 'team lead':
            role = 'team_lead'
        elif role_input == 'project manager':
            role = 'project_manager'
        elif role_input == 'department head':
            role = 'department_head'
        elif role_input == 'senior worker':
            role = 'senior_worker'
        else:
            await update.message.reply_text(
                "Некорректная роль. Введите одну из:\n"
                "• worker\n"
                "• CEO\n"
                "• team_lead\n"
                "• project_manager\n"
                "• department_head\n"
                "• senior_worker\n"
                "• specialist"
            )
            return AWAITING_ROLE

        # Получаем Telegram данные
        user = update.effective_user
        telegram_username = user.username or str(user.id)
        tg_id = user.id

        # Регистрируем пользователя с tg_id
        success = UserModel.register_user(
            name=context.user_data['user_name'],
            telegram_username=telegram_username,
            tg_id=tg_id,
            role=role,
            jira_account=context.user_data['jira_account']
        )

        if success:
            # Получаем зарегистрированного пользователя
            registered_user = UserModel.get_user_by_telegram_username(telegram_username)

            jira_account = context.user_data.get('jira_account')
            user_name = context.user_data.get('user_name')

            if jira_account:
                # Сообщаем пользователю о начале синхронизации с Jira
                await update.message.reply_text(
                    f"Начинаю синхронизацию с Jira для аккаунта {jira_account}...\n"
                    f"Это может занять несколько секунд."
                )

                # Асинхронно обрабатываем данные Jira (только вывод в консоль)
                try:
                    jira_success = await process_jira_registration(
                        user_id=registered_user['id_user'],
                        jira_account=jira_account,
                        user_name=user_name
                    )

                    if jira_success:
                        await update.message.reply_text(
                            "Данные Jira успешно получены!\n"
                            "Проекты и задачи выведены в консоль администратора."
                        )
                    else:
                        await update.message.reply_text(
                            "Не удалось получить данные Jira.\n"
                            "Проверьте правильность Jira аккаунта."
                        )
                except Exception as e:
                    logger.error(f"Ошибка синхронизации Jira: {e}")
                    await update.message.reply_text(
                        "Возникла ошибка при синхронизации с Jira.\n"
                        "Основная регистрация завершена."
                    )
            else:
                await update.message.reply_text(
                    "Jira аккаунт не указан.\n"
                    "Вы можете добавить его позже в профиле."
                )

            # Сохраняем данные в context
            context.user_data['user_role'] = role
            context.user_data['user_id'] = registered_user['id_user']
            context.user_data['user_name'] = registered_user['name']
            context.user_data['jira_account'] = registered_user['jira_account']

            # Показываем успешную регистрацию
            role_display = {
                'worker': 'Рабочий',
                'CEO': 'Руководитель',
                'team_lead': 'Тимлид',
                'project_manager': 'Менеджер проектов',
                'department_head': 'Руководитель отдела',
                'senior_worker': 'Старший рабочий',
                'specialist': 'Специалист'
            }.get(role, role)

            await update.message.reply_text(
                f"Регистрация завершена успешно!\n\n"
                f"Имя: {registered_user['name']}\n"
                f"Роль: {role_display}\n"
                f"Telegram: @{telegram_username}\n\n"
                f"Используйте /help для списка команд."
            )
        else:
            logger.error(f"Ошибка регистрации пользователя {telegram_username}")
            await update.message.reply_text(
                "Ошибка регистрации.\n"
                "Возможные причины:\n"
                "1. Пользователь с таким Telegram уже зарегистрирован\n"
                "2. Проблема с подключением к базе данных\n\n"
                "Обратитесь к администратору."
            )

        # Очищаем данные регистрации
        for key in ['awaiting_role', 'user_name', 'awaiting_password',
                    'awaiting_name', 'awaiting_jira', 'jira_account']:
            context.user_data.pop(key, None)

        return ConversationHandler.END

    # Если пользователь авторизован и отвечает на опрос
    elif context.user_data.get('awaiting_survey_response'):
        from handlers.survey_handlers import handle_survey_response
        return await handle_survey_response(update, context)

    else:
        # Пользователь авторизован, но отправил неизвестную команду
        await update.message.reply_text(
            "Неизвестная команда. Используйте /help для списка команд."
        )


async def start_command(update, context):
    """Обработчик команды /start"""
    user = update.effective_user
    telegram_username = user.username or str(user.id)

    # Проверяем, авторизован ли пользователь
    user_data = UserModel.get_user_by_telegram_username(telegram_username)

    if user_data:
        # Пользователь уже авторизован
        # В функции start_command обновить текст
        role_display = {
            'worker': 'Worker',
            'CEO': 'CEO',
            'team_lead': 'Team Lead',
            'project_manager': 'Project Manager',
            'department_head': 'Department Head',
            'senior_worker': 'Senior Worker',
            'specialist': 'Specialist'
        }.get(user_data['role'], user_data['role'])

        jira_info = f"Jira: {user_data['jira_account']}" if user_data['jira_account'] else "📋 Jira: не указан"

        await update.message.reply_text(
            f"Вы уже авторизованы!\n\n"
            f"{user_data['name']}\n"
            f"Роль: {role_display}\n"
            f"{jira_info}\n\n"
            f"Используйте /help для списка доступных команд."
        )

        # Сохраняем данные в context
        context.user_data['user_role'] = user_data['role']
        context.user_data['user_id'] = user_data['id_user']
        context.user_data['user_name'] = user_data['name']
        context.user_data['jira_account'] = user_data['jira_account']

        return ConversationHandler.END
    else:
        # Начинаем процесс регистрации
        await update.message.reply_text(
            "Добро пожаловать!\n\n"
            "Вы не авторизованы в системе.\n"
            "Для регистрации введите пароль:\n\n"
            "Используйте /cancel для отмены."
        )

        context.user_data['awaiting_password'] = True

        return AWAITING_PASSWORD
