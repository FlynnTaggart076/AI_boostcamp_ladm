# -*- coding: utf-8 -*-
import math
from typing import List, Dict, Tuple
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from tg_bot.config.constants import PAGINATION_ITEMS_PER_PAGE


class PaginationUtils:
    """Утилиты для работы с пагинацией (только чтение)"""

    ITEMS_PER_PAGE = PAGINATION_ITEMS_PER_PAGE

    @staticmethod
    def get_page_items(items: List[Dict], page: int = 0) -> Tuple[List[Dict], int, int]:
        """
        Получить элементы для страницы
        """
        if not items:
            return [], 0, 0

        total_pages = math.ceil(len(items) / PaginationUtils.ITEMS_PER_PAGE)

        # Ограничиваем page в пределах допустимых значений
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1

        start_idx = page * PaginationUtils.ITEMS_PER_PAGE
        end_idx = start_idx + PaginationUtils.ITEMS_PER_PAGE
        page_items = items[start_idx:end_idx]

        return page_items, page, total_pages

    @staticmethod
    def create_pagination_navigation(page: int, total_pages: int, callback_prefix: str) -> InlineKeyboardMarkup:
        """
        Создать клавиатуру только для навигации по страницам
        """
        if total_pages <= 1:
            return None

        keyboard = []
        nav_buttons = []

        # Кнопка "Назад" - только если не на первой странице
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("⬅️ Назад", callback_data=f"{callback_prefix}{page - 1}")
            )
        else:
            # Неактивная кнопка для первой страницы
            nav_buttons.append(
                InlineKeyboardButton("⬅️", callback_data=f"{callback_prefix}{page}")
            )

        # Номер текущей страницы
        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data=f"{callback_prefix}info")
        )

        # Кнопка "Вперед" - только если не на последней странице
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("➡️ Вперед", callback_data=f"{callback_prefix}{page + 1}")
            )
        else:
            # Неактивная кнопка для последней страницы
            nav_buttons.append(
                InlineKeyboardButton("➡️", callback_data=f"{callback_prefix}{page}")
            )

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("✖️ Закрыть", callback_data=f"{callback_prefix}close")])

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def format_page_with_numbers(items: List[Dict], page: int, total_pages: int, title: str) -> str:
        """
        Форматировать сообщение страницы с номерами элементов
        """
        if not items:
            return f"{title}\n\nНет элементов для отображения."

        message = f"{title}\n\n"

        # Нумерация с учетом страницы
        start_num = page * PaginationUtils.ITEMS_PER_PAGE + 1

        for i, item in enumerate(items):
            item_num = start_num + i

            if 'question' in item and 'datetime' in item:
                # Форматирование для опросов
                target = item.get('role', 'все пользователи') if item.get('role') else "все пользователи"
                question_preview = item['question'][:60] + "..." if len(item['question']) > 60 else item['question']
                date_str = item['datetime'].strftime('%d.%m.%Y %H:%M') if hasattr(item['datetime'],
                                                                                  'strftime') else str(item['datetime'])

                if 'user_answer' in item:
                    # Для отвеченных опросов
                    answer_preview = item['user_answer'][:50] + "..." if item['user_answer'] and len(
                        item['user_answer']) > 50 else item['user_answer'] or "(пустой ответ)"
                    message += f"{item_num}. Опрос #{item.get('id_survey', '?')}\n"
                    message += f"   {date_str}\n"
                    message += f"   {question_preview}\n"
                    message += f"   Ответ: {answer_preview}\n\n"
                else:
                    # Для доступных опросов
                    message += f"{item_num}. Опрос #{item.get('id_survey', '?')}\n"
                    message += f"   {date_str}\n"
                    message += f"   {question_preview}\n"
                    message += f"   Для: {target}\n\n"
            else:
                # Для всех опросов (админский просмотр)
                target = item.get('role', 'все') if item.get('role') else 'все'
                question_preview = item.get('question', '')[:60] + "..." if len(
                    item.get('question', '')) > 60 else item.get('question', '')
                date_str = item['datetime'].strftime('%d.%m.%Y %H:%M') if hasattr(item['datetime'],
                                                                                  'strftime') else str(item['datetime'])

                message += f"{item_num}. ID: {item.get('id_survey', '?')}\n"
                message += f"   Вопрос: {question_preview}\n"
                message += f"   Для: {target}\n"
                message += f"   Время: {date_str}\n"
                message += f"   Статус: {item.get('state', '?')}\n\n"

        message += f"Страница {page + 1} из {total_pages}\n"
        message += f"Всего элементов: {len(items)}\n"

        # Добавляем подсказку для выбора только если это нужно (для response и addresponse)
        if 'user_answer' not in items[0] if items else False and 'state' not in items[0] if items else False:
            message += f"\nДля выбора введите номер опроса (например, '{start_num}'):"

        return message

    @staticmethod
    def create_pagination_keyboard(
            items: List[Dict],
            page: int,
            total_pages: int,
            callback_prefix: str,
            with_selection: bool = True
    ) -> InlineKeyboardMarkup:
        """
        Создать клавиатуру пагинации (старый метод, может не использоваться)
        """
        keyboard = []

        # Кнопки выбора элементов (если нужно)
        if with_selection and items:
            for i, item in enumerate(items):
                item_number = page * PaginationUtils.ITEMS_PER_PAGE + i + 1
                button_text = f"{item_number}. {item.get('preview', 'Элемент')}"
                callback_data = f"{callback_prefix}select_{item.get('id', i)}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        # Кнопки навигации
        nav_buttons = []

        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"{callback_prefix}{page - 1}"))

        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data=f"{callback_prefix}info"))

        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"{callback_prefix}{page + 1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("✖️ Отмена", callback_data=f"{callback_prefix}cancel")])

        return InlineKeyboardMarkup(keyboard)
