import logging

import psycopg2

from tg_bot.config.settings import config

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Управление подключениями к БД"""

    _connection_pool = None
    _initialized = False

    def __init__(self):
        self.host = config.DB_HOST
        self.database = config.DB_NAME
        self.user = config.DB_USER
        self.password = config.DB_PASSWORD
        self.port = config.DB_PORT

        if not self._initialized:
            logger.info(f"Параметры подключения к БД:")
            logger.info(f"  Хост: {self.host}")
            logger.info(f"  База данных: {self.database}")
            logger.info(f"  Пользователь: {self.user}")
            logger.info(f"  Порт: {self.port}")
            self._initialized = True

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
            return connection
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            logger.error(f"Параметры: host={self.host}, db={self.database}, user={self.user}, port={self.port}")
            return None


db_connection = DatabaseConnection()
