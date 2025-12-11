# Пароль для регистрации (вынести в .env в будущем)
REGISTRATION_PASSWORD = "secret123"

# Состояния для регистрации пользователя
AWAITING_PASSWORD = 0
AWAITING_NAME = 1
AWAITING_JIRA = 2
AWAITING_ROLE = 3

# Состояния для создания опроса
AWAITING_SURVEY_QUESTION = 10
AWAITING_SURVEY_ROLE = 11
AWAITING_SURVEY_TIME = 12

# Состояния для ответа на опрос
AWAITING_SURVEY_SELECTION = 20
AWAITING_SURVEY_RESPONSE = 21

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
    'worker', 'CEO', 'team_lead', 'project_manager',
    'department_head', 'senior_worker', 'specialist'
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