from tg_bot.config.constants import VALID_ROLES

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
    'CEO': {
        'display_name': 'CEO',
        'description': 'Head of department',
        'permissions': ['create_surveys', 'view_reports', 'manage_users']
    },
    'team_lead': {
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


def get_role_category(role_type):
    """Получить категорию роли (worker/CEO)"""
    # Нормализуем вход
    if role_type == 'CEO':
        return 'CEO'

    if role_type in WORKER_SUBTYPES:
        return 'worker'
    elif role_type in CEO_SUBTYPES:
        return 'CEO'
    else:
        return None


def get_worker_subtypes():
    """Получить все подвиды работников"""
    return list(WORKER_SUBTYPES.keys())


def get_ceo_subtypes():
    """Получить все подвиды руководителей"""
    return list(CEO_SUBTYPES.keys())
