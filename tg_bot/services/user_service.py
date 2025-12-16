# -*- coding: utf-8 -*-
import logging
from typing import Dict, Optional, List
from datetime import datetime

from psycopg2.extras import RealDictCursor

from tg_bot.database.connection import db_connection
from tg_bot.database.models import UserModel
from tg_bot.services.jira_integration import jira_integration
from tg_bot.config.settings import config

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями (база данных + Jira)"""

    @staticmethod
    def find_user_by_jira_account(jira_account: str) -> Optional[Dict]:
        """
        Универсальный поиск пользователя по Jira аккаунту
        Ищет сначала в БД, затем в Jira API при необходимости
        """
        # 1. Поиск в базе данных
        user = UserService._find_in_database(jira_account)
        if user:
            logger.debug(f"Пользователь найден в БД: {jira_account}")
            return user

        # 2. Если не найден и есть доступ к Jira, ищем через API
        if config.JIRA_URL and config.JIRA_EMAIL and config.JIRA_API_TOKEN:
            user = UserService._find_in_jira(jira_account)
            if user:
                logger.debug(f"Пользователь найден в Jira: {jira_account}")
                return user

        return None

    @staticmethod
    def _find_in_database(jira_account: str) -> Optional[Dict]:
        """Поиск пользователя в базе данных"""
        # Проверяем как email
        if '@' in jira_account:
            user = UserModel.get_user_by_jira_email(jira_account)
            if user:
                return user

        # Проверяем как имя
        user = UserModel.get_user_by_jira_name(jira_account)
        if user:
            return user

        # Проверяем как display name (email до @)
        if '@' in jira_account:
            name_part = jira_account.split('@')[0]
            user = UserModel.get_user_by_jira_name(name_part)
            if user:
                return user

        return None

    @staticmethod
    def _find_in_jira(jira_account: str) -> Optional[Dict]:
        """Поиск пользователя через Jira API"""
        try:
            # Ищем через Jira API
            jira_user = jira_integration.find_user_by_display_name(jira_account)

            if jira_user:
                # Сохраняем пользователя в БД для будущих поисков
                user_data = {
                    'jira_name': jira_user.get('display_name'),
                    'jira_email': jira_user.get('email_address')
                }

                user_id = UserModel.save_jira_user(user_data)
                if user_id:
                    # Получаем полную запись из БД
                    connection = db_connection.get_connection()
                    if connection:
                        try:
                            cursor = connection.cursor(cursor_factory=RealDictCursor)
                            cursor.execute("SELECT * FROM users WHERE id_user = %s", (user_id,))
                            user = cursor.fetchone()
                            return dict(user) if user else None
                        finally:
                            cursor.close()
                            connection.close()
        except Exception as e:
            logger.error(f"Ошибка поиска пользователя в Jira: {e}")

        return None

    @staticmethod
    def register_or_update_user(
            name: str,
            telegram_username: str,
            tg_id: int,
            role: str,
            jira_account: str = None
    ) -> Dict:
        """
        Универсальный метод регистрации/обновления пользователя
        Объединяет логику из auth_handlers.py
        """
        result = {
            'success': False,
            'user_id': None,
            'action': None,  # 'created', 'updated', 'exists'
            'message': ''
        }

        # 1. Проверяем, есть ли уже такой Telegram пользователь
        existing_tg_user = UserModel.get_user_by_telegram_username(telegram_username)
        if existing_tg_user:
            result.update({
                'success': True,
                'user_id': existing_tg_user['id_user'],
                'action': 'exists',
                'message': 'Пользователь уже зарегистрирован'
            })
            return result

        # 2. Если указан Jira аккаунт, ищем или создаем
        existing_jira_user = None
        if jira_account:
            existing_jira_user = UserService.find_user_by_jira_account(jira_account)

        # 3. Логика регистрации
        if existing_jira_user:
            # Обновляем существующего пользователя Jira
            success = UserModel.update_existing_jira_user(
                user_id=existing_jira_user['id_user'],
                telegram_username=telegram_username,
                tg_id=tg_id,
                role=role,
                name=name
            )

            if success:
                result.update({
                    'success': True,
                    'user_id': existing_jira_user['id_user'],
                    'action': 'updated',
                    'message': 'Существующий пользователь Jira обновлен'
                })
            else:
                result['message'] = 'Ошибка обновления пользователя Jira'

        else:
            # Создаем нового пользователя
            success = UserModel.register_user(
                name=name,
                telegram_username=telegram_username,
                tg_id=tg_id,
                role=role,
                jira_account=jira_account
            )

            if success:
                user = UserModel.get_user_by_telegram_username(telegram_username)
                if user:
                    result.update({
                        'success': True,
                        'user_id': user['id_user'],
                        'action': 'created',
                        'message': 'Новый пользователь создан'
                    })
            else:
                result['message'] = 'Ошибка регистрации пользователя'

        return result

    @staticmethod
    def get_user_context(telegram_username: str) -> Dict:
        """
        Получение полного контекста пользователя для сохранения в user_data
        """
        user = UserModel.get_user_by_telegram_username(telegram_username)
        if not user:
            return {}

        return {
            'user_id': user['id_user'],
            'user_role': user['role'],
            'user_name': user['user_name'],
            'jira_account': user.get('jira_name') or user.get('jira_email'),
            'telegram_username': user['tg_username'],
            'tg_id': user['tg_id']
        }

    @staticmethod
    def sync_user_jira_data(user_id: int, jira_account: str) -> Dict:
        """
        Синхронизация данных пользователя с Jira
        """
        try:
            # Ищем пользователя в Jira
            jira_user = jira_integration.find_user_by_display_name(jira_account)

            if not jira_user:
                return {
                    'success': False,
                    'message': 'Пользователь не найден в Jira'
                }

            # Получаем проекты пользователя
            projects = jira_integration.get_user_projects_by_account_id(
                jira_user['account_id']
            )

            # Обновляем данные в БД
            connection = db_connection.get_connection()
            if not connection:
                return {
                    'success': False,
                    'message': 'Ошибка подключения к БД'
                }

            try:
                cursor = connection.cursor()
                cursor.execute("""
                    UPDATE users 
                    SET jira_account_id = %s,
                        jira_last_sync = %s
                    WHERE id_user = %s
                """, (jira_user['account_id'], datetime.now(), user_id))
                connection.commit()

                return {
                    'success': True,
                    'message': 'Данные Jira синхронизированы',
                    'projects_count': len(projects),
                    'jira_user': jira_user
                }
            finally:
                cursor.close()
                connection.close()

        except Exception as e:
            logger.error(f"Ошибка синхронизации Jira данных: {e}")
            return {
                'success': False,
                'message': f'Ошибка синхронизации: {str(e)}'
            }


# Глобальный экземпляр сервиса
user_service = UserService()