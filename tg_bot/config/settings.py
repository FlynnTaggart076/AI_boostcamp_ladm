import os
import logging
from dotenv import load_dotenv

env_path = '.env'
if os.path.exists(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except UnicodeDecodeError:
        try:
            with open(env_path, 'r', encoding='cp1251') as f:
                content = f.read()
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except:
            pass

load_dotenv()
logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        required_vars = ['BOT_TOKEN', 'DB_HOST', 'DB_NAME', 'REGISTRATION_PASSWORD']
        for var in required_vars:
            if not getattr(self, var):
                raise ValueError(f"Отсутствует обязательная переменная: {var}")

        if self.JIRA_URL:
            jira_vars = ['JIRA_EMAIL', 'JIRA_API_TOKEN']
            for var in jira_vars:
                if not getattr(self, var):
                    logger.warning(f"⚠ Jira переменная {var} не установлена")

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    REGISTRATION_PASSWORD = os.getenv("REGISTRATION_PASSWORD")

    JIRA_URL = os.getenv("JIRA_URL")
    JIRA_EMAIL = os.getenv("JIRA_EMAIL")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

    JIRA_SYNC_ON_START = os.getenv("JIRA_SYNC_ON_START", "true").lower() == "true"
    JIRA_SYNC_DAYS_BACK = int(os.getenv("JIRA_SYNC_DAYS_BACK", "365"))
    JIRA_CLEAR_OLD_DATA = os.getenv("JIRA_CLEAR_OLD_DATA", "false").lower() == "true"
    JIRA_MAX_TASKS = int(os.getenv("JIRA_MAX_TASKS", "1000"))

    ALLSURVEYS_PERIOD_DAYS = int(os.getenv('ALLSURVEYS_PERIOD_DAYS', '30'))
    RESPONSE_PERIOD_DAYS = int(os.getenv('RESPONSE_PERIOD_DAYS', '14'))
    ADDRESPONSE_PERIOD_DAYS = int(os.getenv('ADDRESPONSE_PERIOD_DAYS', '14'))

    PAGINATION_ITEMS_PER_PAGE = int(os.getenv('PAGINATION_ITEMS_PER_PAGE', '5'))
    PAGINATION_MAX_ITEMS = int(os.getenv('PAGINATION_MAX_ITEMS', '200'))
    PAGINATION_ENABLED = os.getenv('PAGINATION_ENABLED', 'true').lower() == 'true'

    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


config = Config()
