from datetime import datetime
from config.constants import VALID_ROLES  # Добавляем импорт

def validate_date(date_string, date_format="%Y-%m-%d"):
    """Валидация даты"""
    # TODO: добавить поддержку разных форматов дат
    # TODO: добавить проверку на будущие даты
    try:
        datetime.strptime(date_string, date_format)
        return True
    except ValueError:
        return False

def validate_time(time_string, time_format="%H:%M"):
    """Валидация времени"""
    # TODO: реализовать валидацию времени
    try:
        datetime.strptime(time_string, time_format)
        return True
    except ValueError:
        return False

def validate_survey_topic(topic):
    """Валидация темы опроса"""
    # TODO: добавить проверку длины темы
    # TODO: добавить проверку запрещенных символов
    if not topic or len(topic.strip()) < 3:
        return False
    return True

def validate_username(username):
    """Валидация имени пользователя"""
    # TODO: добавить проверку на допустимые символы
    # TODO: добавить проверку длины
    if not username:
        return False
    return True

def validate_role(role):
    """Валидация роли пользователя"""
    # Проверяем, что роль в списке допустимых
    return role in VALID_ROLES

def validate_jira_account(jira_account):
    """Валидация Jira аккаунта"""
    # TODO: добавить проверку формата email или логина
    # Пока просто проверяем, что не пустая строка
    if not jira_account or jira_account.strip() == '':
        return False
    return True

# TODO: добавить валидаторы для других типов данных
