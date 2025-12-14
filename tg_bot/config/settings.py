import os
from dotenv import load_dotenv
import logging
load_dotenv()
logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        # Проверяем обязательные настройки
        required_vars = ['BOT_TOKEN', 'DB_HOST', 'DB_NAME']
        for var in required_vars:
            if not getattr(self, var):
                raise ValueError(f"❌ Отсутствует обязательная переменная: {var}")

        # Проверяем Jira настройки если они нужны
        if self.JIRA_URL:
            jira_vars = ['JIRA_EMAIL', 'JIRA_API_TOKEN']
            for var in jira_vars:
                if not getattr(self, var):
                    logger.warning(f"⚠️ Jira переменная {var} не установлена")


    BOT_TOKEN = os.getenv("BOT_TOKEN", "8344653349:AAEVxNJr12XDg2UvEOmWW4PzCllM_U3AFX8")

    DB_HOST = os.getenv("DB_HOST", "172.24.7.12")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "ladm")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "fpWemPBaTESWv1tIsnej")

    JIRA_URL = os.getenv("JIRA_URL")
    JIRA_EMAIL = os.getenv("JIRA_EMAIL")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

config = Config()