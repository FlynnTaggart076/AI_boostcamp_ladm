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
