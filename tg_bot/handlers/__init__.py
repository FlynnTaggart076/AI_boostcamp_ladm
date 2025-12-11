"""
Пакет обработчиков бота
"""

from . import auth_handlers
from . import survey_handlers
from . import report_handlers
from . import scheduler

__all__ = ['auth_handlers', 'survey_handlers', 'report_handlers', 'scheduler']