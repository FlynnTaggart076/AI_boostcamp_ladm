from tg_bot.config.settings import config

REGISTRATION_PASSWORD = config.REGISTRATION_PASSWORD

# Состояния для регистрации пользователя
AWAITING_PASSWORD = 0
AWAITING_NAME = 1
AWAITING_JIRA = 2
AWAITING_ROLE = 3
AWAITING_SUBROLE = 4

# Состояния для создания опроса - ОБНОВЛЕНО
AWAITING_SURVEY_QUESTION = 10
AWAITING_SURVEY_TARGET = 11
AWAITING_SURVEY_SUBTARGET = 12
AWAITING_SURVEY_TIME = 13
AWAITING_SURVEY_ROLE = 14  # Добавлено для текстового ввода роли

# Состояния для ответа на опрос
AWAITING_SURVEY_SELECTION = 20
AWAITING_SURVEY_RESPONSE = 21
AWAITING_SURVEY_RESPONSE_PART = 22

AWAITING_ADD_RESPONSE_SELECTION = 30
AWAITING_ADD_RESPONSE_PART = 31

AWAITING_REPORT = 40
REPORT_MENU_PREFIX = "report_menu_"

# Настройки периодов из конфига
ALLSURVEYS_PERIOD_DAYS = config.ALLSURVEYS_PERIOD_DAYS
RESPONSE_PERIOD_DAYS = config.RESPONSE_PERIOD_DAYS
ADDRESPONSE_PERIOD_DAYS = config.ADDRESPONSE_PERIOD_DAYS

# Настройки пагинации
PAGINATION_ITEMS_PER_PAGE = config.PAGINATION_ITEMS_PER_PAGE
PAGINATION_MAX_ITEMS = config.PAGINATION_MAX_ITEMS
PAGINATION_ENABLED = config.PAGINATION_ENABLED

PAGINATION_PREFIX = "page_"
SURVEY_PAGINATION_PREFIX = "survey_page_"
ADD_RESPONSE_PAGINATION_PREFIX = "addresponse_page_"
ALLSURVEYS_PAGINATION_PREFIX = "allsurveys_page_"

# Префиксы для callback_data при выборе ролей
CATEGORY_SELECTION_PREFIX = "cat_"
SUBTYPE_SELECTION_PREFIX = "sub_"

# Префиксы для выбора получателей опроса - НОВЫЕ
SURVEY_TARGET_PREFIX = "survey_target_"
SURVEY_SUBTARGET_PREFIX = "survey_subtarget_"

# Роли пользователей (для проверок)
ROLES = {
    'WORKER': 'worker',
    'CEO': 'CEO',
    'TEAM_LEAD': 'team_lead',
    'PROJECT_MANAGER': 'project_manager',
    'DEPARTMENT_HEAD': 'department_head',
    'SENIOR_WORKER': 'senior_worker',
    'SPECIALIST': 'specialist'
}

# Категории ролей
ROLE_CATEGORIES = {
    'WORKERS': ['worker', 'senior_worker', 'specialist'],
    'MANAGERS': ['CEO', 'team_lead', 'project_manager', 'department_head']
}

# Валидные роли для БД
VALID_ROLES = [
    'worker',
    'CEO',
    'team_lead',
    'project_manager',
    'department_head',
    'senior_worker',
    'specialist'
]

# Статусы опросов
SURVEY_STATUS = {
    'ACTIVE': 'active',
    'CLOSED': 'closed',
    'DRAFT': 'draft'
}

# Статусы спринтов
SPRINT_STATUS = {
    'ACTIVE': 'active',
    'CLOSED': 'closed'
}

# ========== ДОБАВЛЕННЫЕ КОНСТАНТЫ ==========

# Максимальные длины для валидации
MAX_NAME_LENGTH = 50
MIN_NAME_LENGTH = 2
MAX_JIRA_LENGTH = 100
MIN_JIRA_LENGTH = 3
MAX_SURVEY_QUESTION_LENGTH = 1000
MIN_SURVEY_QUESTION_LENGTH = 5
MAX_RESPONSE_LENGTH = 5000
MIN_RESPONSE_LENGTH = 3
MAX_PASSWORD_LENGTH = 50
MIN_PASSWORD_LENGTH = 8

# Форматы дат и времени
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M'
DISPLAY_DATE_FORMAT = '%d.%m.%Y'
DISPLAY_DATETIME_FORMAT = '%d.%m.%Y %H:%M'

# Настройки напоминаний
REMINDER_STAGES = {
    1: 'first_reminder',  # Первое напоминание
    2: 'second_reminder', # Второе напоминание
    3: 'final_reminder'   # Финальное напоминание
}

REMINDER_INTERVALS = {
    1: 30,  # 1 час в секундах 3600
    2: 45,  # 2 часа в секундах 7200
    3: 45   # 2 часа в секундах 7200
}

# Настройки планировщика
SCHEDULER_CHECK_INTERVAL = 30  # Интервал проверки в секундах
SCHEDULER_BATCH_SIZE = 50  # Размер пакета для отправки

# Ограничения для отчетов
MAX_REPORT_PERIOD_DAYS = 365  # Максимальный период для отчетов
DEFAULT_REPORT_PERIOD_DAYS = 30  # Период по умолчанию

# Коды ошибок
ERROR_CODES = {
    'VALIDATION_ERROR': 'VALIDATION_ERROR',
    'PERMISSION_DENIED': 'PERMISSION_DENIED',
    'NOT_FOUND': 'NOT_FOUND',
    'DATABASE_ERROR': 'DATABASE_ERROR',
    'SCHEDULER_ERROR': 'SCHEDULER_ERROR'
}

# Режимы работы
BOT_MODES = {
    'PRODUCTION': 'production',
    'DEVELOPMENT': 'development',
    'TESTING': 'testing'
}

# Регулярные выражения
REGEX_PATTERNS = {
    'EMAIL': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'JIRA_NAME': r'^[a-zA-Zа-яА-ЯёЁ0-9._\s-]+$',
    'USER_NAME': r'^[a-zA-Zа-яА-ЯёЁ\s-]{2,50}$',
    'TIME': r'^(\d{1,2}):(\d{2})$',
    'DATE': [
        r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
        r'^\d{2}\.\d{2}\.\d{4}$'  # DD.MM.YYYY
    ]
}

# Команды бота
BOT_COMMANDS = {
    'START': 'start',
    'HELP': 'help',
    'RESPONSE': 'response',
    'SENDSURVEY': 'sendsurvey',
    'REPORT': 'report',
    'CANCEL': 'cancel',
    'DONE': 'done',
    'STOP': 'stop'
}

# Типы контента
CONTENT_TYPES = {
    'TEXT': 'text',
    'PHOTO': 'photo',
    'DOCUMENT': 'document',
    'VIDEO': 'video',
    'AUDIO': 'audio'
}

# Настройки безопасности
SECURITY_SETTINGS = {
    'MAX_LOGIN_ATTEMPTS': 3,
    'SESSION_TIMEOUT': 3600,  # 1 час в секундах
    'PASSWORD_HASH_ROUNDS': 12
}

# Флаги фич
FEATURE_FLAGS = {
    'ENABLE_REMINDERS': True,
    'ENABLE_PAGINATION': True,
    'ENABLE_REPORTS': True,
    'ENABLE_MULTIPART_RESPONSES': True
}

# Типы событий для логирования
LOG_EVENTS = {
    'USER_REGISTRATION': 'user_registration',
    'SURVEY_CREATION': 'survey_creation',
    'SURVEY_RESPONSE': 'survey_response',
    'REMINDER_SENT': 'reminder_sent',
    'ERROR_OCCURRED': 'error_occurred'
}

# Уровни доступа
ACCESS_LEVELS = {
    'ADMIN': 100,
    'MANAGER': 50,
    'USER': 10,
    'GUEST': 0
}