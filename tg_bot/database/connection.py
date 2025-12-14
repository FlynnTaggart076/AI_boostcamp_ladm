import psycopg2
from psycopg2 import pool
from tg_bot.config.settings import config
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Управление подключениями к БД"""

    _connection_pool = None

    def __init__(self):
        # TODO: реализовать connection pool для лучшей производительности
        # TODO: добавить retry логику при ошибках подключения
        self.host = config.DB_HOST
        self.database = config.DB_NAME
        self.user = config.DB_USER
        self.password = config.DB_PASSWORD
        self.port = config.DB_PORT

    def get_connection(self):
        """Создание подключения к БД"""
        try:
            connection = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port,
                connect_timeout=10
            )
            logger.info(f"✅ Успешное подключение к БД: {self.database}@{self.host}")
            return connection
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            logger.error(f"Параметры: host={self.host}, db={self.database}, user={self.user}, port={self.port}")
            return None

    def close_all_connections(self):
        """Закрытие всех подключений"""
        # TODO: реализовать при использовании connection pool
        pass


db_connection = DatabaseConnection()