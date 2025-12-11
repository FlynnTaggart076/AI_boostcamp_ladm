from config.constants import VALID_ROLES  # Импортируем для consistency

# Подвиды работников (worker)
WORKER_SUBTYPES = {
    'worker': {
        'display_name': 'Worker',
        'description': 'Basic worker, performs tasks',
        'permissions': ['respond_to_surveys', 'view_own_tasks']
    },
    'senior_worker': {
        'display_name': 'Senior Worker',
        'description': 'Experienced worker with additional responsibilities',
        'permissions': ['respond_to_surveys', 'view_team_tasks', 'report_blockers']
    },
    'specialist': {
        'display_name': '🔧 Specialist',
        'description': 'Specialist in a specific area',
        'permissions': ['respond_to_surveys', 'view_special_tasks', 'technical_reports']
    }
}

CEO_SUBTYPES = {
    'CEO': {  # Всегда заглавными
        'display_name': 'CEO',
        'description': 'Head of department',
        'permissions': ['create_surveys', 'view_reports', 'manage_users']
    },
    'team_lead': {  # строчными
        'display_name': 'Team Lead',
        'description': 'Team leader',
        'permissions': ['create_surveys', 'view_reports', 'manage_team', 'assign_tasks']
    },
    'project_manager': {
        'display_name': 'Project Manager',
        'description': 'Manages projects and deadlines',
        'permissions': ['create_surveys', 'view_reports', 'manage_projects', 'set_deadlines']
    },
    'department_head': {
        'display_name': 'Department Head',
        'description': 'Department manager',
        'permissions': ['create_surveys', 'view_reports', 'manage_department', 'budget_control']
    }
}

ALL_ROLES = {**WORKER_SUBTYPES, **CEO_SUBTYPES}

ROLE_CATEGORIES = {
    'worker': {
        'name': 'Workers',
        'subtypes': WORKER_SUBTYPES
    },
    'CEO': {  # Заглавными
        'name': 'Managers',
        'subtypes': CEO_SUBTYPES
    }
}

def get_role_display_name(role_type):
    """Получить отображаемое имя роли"""
    role = ALL_ROLES.get(role_type)
    return role['display_name'] if role else role_type

def get_role_description(role_type):
    """Получить описание роли"""
    role = ALL_ROLES.get(role_type)
    return role['description'] if role else 'No description available'

def get_role_permissions(role_type):
    """Получить разрешения роли"""
    role = ALL_ROLES.get(role_type)
    return role.get('permissions', []) if role else []

def get_available_roles():
    """Получить список всех доступных ролей"""
    return list(ALL_ROLES.keys())

def get_worker_subtypes():
    """Получить все подвиды работников"""
    return list(WORKER_SUBTYPES.keys())

def get_ceo_subtypes():
    """Получить все подвиды руководителей"""
    return list(CEO_SUBTYPES.keys())

def is_valid_role(role_type):
    """Проверить, является ли роль валидной"""
    return role_type in VALID_ROLES  # Используем константы для consistency

def get_role_category(role_type):
    """Получить категорию роли (worker/CEO)"""
    if role_type in WORKER_SUBTYPES:
        return 'worker'
    elif role_type in CEO_SUBTYPES:
        return 'CEO'  # Заглавными
    else:
        return None