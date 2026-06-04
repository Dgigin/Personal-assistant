# -*- coding: utf-8 -*-
"""
Модель для работы со справочником статей расходов (expense_articles.json).

Структура JSON:
{
    "код_столбца": {
        "name": "Название статьи",
        "budget": "Бюджет/КВР"
    }
}
"""

import os
from typing import Dict, Any

from ..utils.json_utils import load_json, save_json


EXPENSE_ARTICLES_FILENAME = "expense_articles.json"


def get_expense_articles_path(config_dir: str) -> str:
    return os.path.join(config_dir, EXPENSE_ARTICLES_FILENAME)


def load_expense_articles(config_dir: str) -> Dict[str, Dict[str, str]]:
    """Загружает справочник статей расходов."""
    path = get_expense_articles_path(config_dir)
    data = load_json(path, {})
    if not isinstance(data, dict):
        return {}
    return data


def save_expense_articles(config_dir: str, articles: Dict[str, Dict[str, str]]) -> None:
    """Сохраняет справочник статей расходов."""
    path = get_expense_articles_path(config_dir)
    save_json(path, articles)
