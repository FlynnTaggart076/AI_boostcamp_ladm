# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from typing import Tuple, Optional
import logging

from tg_bot.config.constants import VALID_ROLES

logger = logging.getLogger(__name__)


class Validator:
    """Централизованный класс для валидации данных"""

    # Регулярные выражения
    NAME_REGEX = r'^[a-zA-Zа-яА-ЯёЁ\s-]{2,50}$'
    TIME_REGEX = r'^(\d{1,2}):(\d{2})$'
    DATE_REGEXES = [
        r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
        r'^\d{2}\.\d{2}\.\d{4}$'  # DD.MM.YYYY
    ]

    @staticmethod
    def validate_user_name(name: str) -> Tuple[bool, str]:
        """Валидация имени пользователя"""
        if not name or len(name.strip()) < 2:
            return False, "Имя должно содержать минимум 2 символа"

        if len(name.strip()) > 50:
            return False, "Имя не должно превышать 50 символов"

        if not re.match(Validator.NAME_REGEX, name):
            return False, "Имя содержит недопустимые символы"

        return True, ""

    @staticmethod
    def validate_jira_account(jira_account: str) -> Tuple[bool, str]:
        """Валидация Jira аккаунта - ПРОСТАЯ ВЕРСИЯ БЕЗ ОГРАНИЧЕНИЙ"""
        if not jira_account or jira_account.strip() == '':
            return True, ""  # Пустой аккаунт допустим

        # Убираем лишние пробелы
        jira_account = jira_account.strip()

        # Если пользователь ввел специальные ключевые слова для пропуска
        skip_keywords = ['нет', 'н', 'no', 'n', 'skip', 'пропустить']
        if jira_account.lower() in skip_keywords:
            return True, ""

        # Принимаем ЛЮБОЙ ввод - ищем в БД как есть
        return True, ""

    @staticmethod
    def validate_role(role_input: str) -> Tuple[bool, str, Optional[str]]:
        """Валидация и нормализация роли"""
        if not role_input:
            return False, "Роль не указана", None

        role_input = role_input.strip().lower()

        # Маппинг ввода пользователя на нормализованные роли
        role_mapping = {
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
            'specialist': 'specialist',
            'руководитель': 'CEO',
            'работник': 'worker',
            'тимлид': 'team_lead',
            'менеджер проектов': 'project_manager',
            'руководитель отдела': 'department_head',
            'старший рабочий': 'senior_worker'
        }

        normalized_role = role_mapping.get(role_input, role_input)

        if normalized_role not in VALID_ROLES:
            valid_roles_str = ', '.join(VALID_ROLES)
            return False, f"Некорректная роль. Допустимые: {valid_roles_str}", None

        return True, "", normalized_role

    @staticmethod
    def validate_survey_question(question: str) -> Tuple[bool, str]:
        """Валидация вопроса опроса"""
        if not question or len(question.strip()) < 5:
            return False, "Вопрос должен содержать минимум 5 символов"

        if len(question.strip()) > 1000:
            return False, "Вопрос не должен превышать 1000 символов"

        # Проверка на запрещенные слова/символы
        forbidden_patterns = [
            r'<script>', r'javascript:', r'onload=', r'onerror=',
            r'SELECT.*FROM', r'INSERT.*INTO', r'DELETE.*FROM',
            r'UPDATE.*SET', r'DROP.*TABLE'
        ]

        for pattern in forbidden_patterns:
            if re.search(pattern, question, re.IGNORECASE):
                return False, "Вопрос содержит недопустимые выражения"

        return True, ""

    @staticmethod
    def validate_survey_time(time_input: str) -> Tuple[bool, str, Optional[datetime]]:
        """Валидация времени отправки опроса"""
        time_input = time_input.strip().lower()
        now = datetime.now()

        try:
            if time_input == 'сейчас':
                send_time = now
                return True, "", send_time

            # Обработка "сегодня/завтра HH:MM"
            today_match = re.match(r'сегодня\s+(\d{1,2}):(\d{2})', time_input)
            tomorrow_match = re.match(r'завтра\s+(\d{1,2}):(\d{2})', time_input)

            if today_match:
                hour, minute = map(int, today_match.groups())
                send_time = datetime(now.year, now.month, now.day, hour, minute)

            elif tomorrow_match:
                hour, minute = map(int, tomorrow_match.groups())
                tomorrow = now + timedelta(days=1)
                send_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute)

            else:
                # Пытаемся распарсить как полную дату
                for fmt in ['%Y-%m-%d %H:%M', '%d.%m.%Y %H:%M', '%Y-%m-%d', '%d.%m.%Y']:
                    try:
                        if ':' in time_input and '%H:%M' not in fmt:
                            continue
                        send_time = datetime.strptime(time_input, fmt)
                        if '%H:%M' not in fmt:
                            # Если время не указано, устанавливаем 9:00
                            send_time = send_time.replace(hour=9, minute=0)
                        break
                    except ValueError:
                        continue
                else:
                    return False, "Неверный формат времени", None

            # Проверка корректности времени
            if not (0 <= send_time.hour < 24 and 0 <= send_time.minute < 60):
                return False, "Некорректное время", None

            # Проверка что время не в прошлом (кроме "сейчас")
            if time_input != 'сейчас' and send_time < now:
                return False, "Время отправки не может быть в прошлом", None

            return True, "", send_time

        except Exception as e:
            logger.error(f"Ошибка валидации времени: {e}")
            return False, f"Ошибка обработки времени: {str(e)}", None

    @staticmethod
    def validate_response_text(response: str) -> Tuple[bool, str]:
        """Валидация текста ответа на опрос"""
        if not response or len(response.strip()) < 3:
            return False, "Ответ должен содержать минимум 3 символа"

        if len(response.strip()) > 5000:
            return False, "Ответ не должен превышать 5000 символов"

        return True, ""

    @staticmethod
    def validate_date_string(date_str: str, date_format: str = "%Y-%m-%d") -> Tuple[bool, str]:
        """Валидация строки даты"""
        try:
            datetime.strptime(date_str, date_format)
            return True, ""
        except ValueError:
            return False, f"Неверный формат даты. Используйте {date_format}"

    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """Валидация пароля (если будет использоваться)"""
        if len(password) < 8:
            return False, "Пароль должен содержать минимум 8 символов"

        if not any(c.isupper() for c in password):
            return False, "Пароль должен содержать хотя бы одну заглавную букву"

        if not any(c.isdigit() for c in password):
            return False, "Пароль должен содержать хотя бы одну цифру"

        return True, ""


# Упрощенные функции для обратной совместимости
def validate_date(date_string, date_format="%Y-%m-%d"):
    """Валидация даты"""
    try:
        datetime.strptime(date_string, date_format)
        return True
    except ValueError:
        return False


def validate_time(time_string, time_format="%H:%M"):
    """Валидация времени"""
    try:
        datetime.strptime(time_string, time_format)
        return True
    except ValueError:
        return False


def validate_survey_topic(topic):
    """Валидация темы опроса"""
    if not topic or len(topic.strip()) < 3:
        return False
    return True


def validate_username(username):
    """Валидация имени пользователя"""
    if not username:
        return False
    return True


def validate_role_old(role):
    """Валидация роли пользователя"""
    return role in VALID_ROLES


def validate_jira_account_old(jira_account):
    """Валидация Jira аккаунта - всегда True"""
    return True  # Принимаем любой ввод
