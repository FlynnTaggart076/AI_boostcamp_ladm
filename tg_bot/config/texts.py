REGISTRATION_TEXTS = {
    'welcome': "Добро пожаловать!\n\nВы не авторизованы в системе.\nДля регистрации введите пароль:\n\nИспользуйте /cancel для отмены.",
    'password_correct': "Пароль верный!\n\nТеперь введите ваше полное имя (ФИО):\nПример: Иванов Иван Иванович\n\nИспользуйте /cancel для отмены.",
    'password_wrong': "Неверный пароль. Попробуйте снова или используйте /cancel:",
    'name_saved': "Имя сохранено!\n\nТеперь введите ваш Jira аккаунт (имя или email):\nПример: ivan.ivanov@company.com\nИли: iivanov\n\nЕсли у вас нет Jira аккаунта, введите 'нет' или пропустите.",
    'jira_saved': "Jira account saved!\n\nChoose your role:",
    'role_options': """уководители (могут создавать опросы, просматривать отчеты и синхронизировать с Jira):
• CEO - руководитель
• team_lead - тимлид
• project_manager - менеджер проектов
• department_head - руководитель отдела\n\n
Работники (могут отвечать на опросы):
• worker - базовый работник
• senior_worker - старший рабочий
• specialist - специалист\n\n
Enter role name (English only):""",
    'invalid_role': "Некорректная роль. Введите одну из:\n• worker\n• CEO\n• team_lead\n• project_manager\n• department_head\n• senior_worker\n• specialist",
    'registration_complete': "Регистрация завершена успешно!\n\nИмя: {name}\nРоль: {role}\nTelegram: @{username}\n\nИспользуйте /help для списка команд.",
    'already_registered': "Вы уже авторизованы!\n\n{name}\nРоль: {role}\n{jira_info}\n\nИспользуйте /help для списка доступных команд.",

    # НОВЫЕ ТЕКСТЫ
    'jira_user_found': "Найден пользователь Jira: {jira_name}\nТеперь выберите вашу роль в системе:",
    'jira_user_not_found': "ℹПользователь с Jira аккаунтом '{jira_account}' не найден в системе.\nБудет создан новый профиль.",
    'jira_user_already_registered': "Пользователь с Jira аккаунтом '{jira_account}' уже зарегистрирован в Telegram.\nЕсли это вы, используйте /start с тем же Telegram аккаунтом.",
    'updating_existing_user': "Обновление данных существующего пользователя Jira...",
    'creating_new_user': "Создание нового профиля...",
}

AUTH_TEXTS = {
    'not_authorized': "Сначала авторизуйтесь с помощью /start",
    'unknown_role': "Неизвестная роль. Обратитесь к администратору.",
    'no_permission': "У вас нет прав для выполнения этой команды.\nВаша роль: {role}\nТребуемая категория: {required}"
}

SURVEY_TEXTS = {
    'create_welcome': "Создание нового опроса\n\nШаг 1 из 3: Введите вопрос для опроса:\n\nПример: 'Что вы сделали сегодня?'\nИли: 'Какие проблемы возникли за неделю?'\n\nИспользуйте /cancel для отмены.",
    'question_saved': "Вопрос сохранен!\n\nШаг 2 из 3: Кому отправить опрос?\n\nВведите:\n• 'all' - всем пользователям\n• Или конкретную роль: ceo, worker, team_lead, project_manager, department_head, senior_worker, specialist\n\nПример: 'all' или 'worker'\nИспользуйте /cancel для отмены.",
    'no_users_for_role': "Нет пользователей с ролью '{role}' с привязанными Telegram аккаунтами.\nВыберите другую роль:",
    'no_users_registered': "Нет пользователей с привязанными Telegram аккаунтами.\nСначала зарегистрируйте пользователей.",
    'role_saved': "Опрос будет отправлен {count} пользователям ({role_display}).\n\nШаг 3 из 3: Когда отправить опрос?\n\nВведите дату и время в формате:\n• 'сегодня 14:30' - сегодня в 14:30\n• 'завтра 09:00' - завтра в 9 утра\n• '2024-01-20 18:00' - конкретная дата\n• 'сейчас' - отправить немедленно\n\nПример: 'завтра 10:00'\nИспользуйте /cancel для отмены.",
    'invalid_time': "Ошибка распознавания времени: {error}\nПопробуйте снова в формате:\n• 'сегодня 14:30'\n• 'завтра 09:00'\n• '2024-01-20 18:00'\n• 'сейчас'",
    'past_time': "Время отправки не может быть в прошлом.\nПопробуйте снова:",
    'survey_created': "Опрос успешно создан!\n\nID опроса: {id}\nВопрос: {question}\nПолучатели: {role} ({count} чел.)\nОтправка: {time} ({type})\n\nОпрос будет отправлен автоматически в указанное время.",
    'survey_error': "Ошибка при создании опроса. Попробуйте снова позже.",
    'no_active_surveys': "No active surveys available for response.",
    'all_surveys_answered': "You have already answered all available surveys."
}

HELP_TEXTS = {
    'ceo': """Руководители (CEO/Team Lead/Project Manager и др.) - доступные команды:

Просмотр отчетов:
/dailydigest [дата] - ежедневный дайджест
/weeklydigest [начало] [конец] - еженедельный дайджест  
/blockers [дата] - список блокеров

Управление опросами:
/sendsurvey - создать и отправить опрос
/mysurveys - просмотреть созданные опросы

Синхронизация:
/syncjira - синхронизация данных с Jira

Ответы на опросы:
/response - ответить на опрос

Общие команды:
/profile - просмотр профиля
/cancel - отмена текущей операции
/help - эта справка""",

    'worker': """Работники (Worker/Senior Worker/Specialist и др.) - доступные команды:

Ответы на опросы:
/response - ответить на опрос от руководителя

Общие команды:
/profile - просмотр профиля
/cancel - отмена текущей операции
/help - эта справка""",

    'unknown_category': "Неизвестная категория роли. Обратитесь к администратору."
}

PROFILE_TEXTS = {
    'profile_title': "Ваш профиль:\n\n",
    'no_jira': "Jira: не указан",
    'with_jira': "Jira: {account}"
}

JIRA_TEXTS = {
    'syncing': "Начинаю синхронизацию с Jira для {account}...",
    'success': "Синхронизация с Jira завершена успешно!\nВсе проекты, задачи и спринты обновлены.",
    'no_account': "У вас не указан Jira аккаунт.\nИспользуйте команду /profile для просмотра профиля.",
    'error': "Не удалось синхронизировать с Jira.\nПроверьте правильность Jira аккаунта или обратитесь к администратору.",
    'sync_error': "Произошла ошибка при синхронизации.\nПопробуйте позже или обратитесь к администратору."
}

# Словари для отображения ролей
ROLE_DISPLAY = {
    'worker': 'Рабочий',
    'CEO': 'Руководитель',
    'team_lead': 'Тимлид',
    'project_manager': 'Менеджер проектов',
    'department_head': 'Руководитель отдела',
    'senior_worker': 'Старший рабочий',
    'specialist': 'Специалист'
}

ROLE_DISPLAY_EN = {
    'worker': 'Worker',
    'CEO': 'CEO',
    'team_lead': 'Team Lead',
    'project_manager': 'Project Manager',
    'department_head': 'Department Head',
    'senior_worker': 'Senior Worker',
    'specialist': 'Specialist'
}

CATEGORY_DISPLAY = {
    'worker': 'Работники',
    'CEO': 'Руководители'
}

# Другие тексты
GENERAL_TEXTS = {
    'unknown_command': "Неизвестная команда. Используйте /help для списка команд.",
    'cancelled': "Регистрация отменена. Используйте /start для повторной попытки.",
    'survey_cancelled': "Создание опроса отменено.",
    'db_connection_error': "Ошибка подключения к БД",
    'jira_connection_error': "Ошибка подключения к Jira"
}

# Важные функции, которые нужно сохранить
def get_role_display_name(role_type):
    """Получить отображаемое имя роли на русском"""
    return ROLE_DISPLAY.get(role_type, role_type)

def get_role_display_name_en(role_type):
    """Получить отображаемое имя роли на английском"""
    return ROLE_DISPLAY_EN.get(role_type, role_type)

def get_category_display(category):
    """Получить отображаемое имя категории"""
    return CATEGORY_DISPLAY.get(category, category)

def format_profile(name, role, jira_account=None, chat_id=None):
    """Форматировать профиль пользователя"""
    role_display = get_role_display_name(role)
    jira_info = f"Jira: {jira_account}" if jira_account else PROFILE_TEXTS['no_jira']

    profile = f"Ваш профиль:\n\nИмя: {name}\nРоль: {role_display}\n{jira_info}"

    if chat_id:
        profile += f"\nTelegram Chat ID: {chat_id}"

    return profile

def format_registration_complete(name, role, username):
    """Форматировать сообщение об успешной регистрации"""
    role_display = get_role_display_name(role)
    return REGISTRATION_TEXTS['registration_complete'].format(
        name=name, role=role_display, username=username
    )