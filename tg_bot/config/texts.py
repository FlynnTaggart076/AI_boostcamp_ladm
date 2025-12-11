"""Текстовые сообщения бота с учетом ролей"""

ROLE_DISPLAY_NAMES = {
    'CEO': 'CEO',
    'worker': 'Worker',
    'team_lead': 'Team Lead',
    'project_manager': 'Project Manager',
    'department_head': 'Department Head',
    'senior_worker': 'Senior Worker',
    'specialist': 'Specialist'
}

HELP_TEXTS = {
    "start": "Добро пожаловать! Используйте /start для авторизации по ФИО.",

    "auth_success": "Авторизация успешна!",
    "auth_failed": "Пользователь не найден. Обратитесь к администратору.",
    "auth_required": "Требуется авторизация. Используйте /start",

    "CEO_help": """
     CEO - available commands:
    
    view reports:
    /dailydigest [date] - daily digest
    /weeklydigest [start] [end] - weekly digest  
    /blockers [date] - blockers list
    
     Survey management:
    /sendsurvey - create and send survey
    
     Survey responses:
    /response - respond to surveys (for testing)
    """,

        "worker_help": """
     Worker - available commands:
    
     Survey responses:
    /response - respond to surveys from manager
    You will see a list of all available surveys.
    """,

    "role_no_access": " У вас нет прав для выполнения этой команды.",

    "survey_created": " Опрос создан и отправлен рабочим!",
    "response_mode": " Режим ответа на опрос активирован. Введите ваш ответ:",

    "report_instruction": " Используйте команду с датой в формате ГГГГ-ММ-ДД",
    "blockers_report": "Отчет по блокерам"
}

def get_text(key, default=None):
    """Получение текста по ключу"""
    return HELP_TEXTS.get(key, default or f"Текст '{key}' не найден")

def get_role_display(role):
    """Получение отображаемого названия роли"""
    return ROLE_DISPLAY_NAMES.get(role, role)