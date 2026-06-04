# -*- coding: utf-8 -*-
"""
Модель для работы со справочником подразделений (departments.json).
"""

import os
from typing import Dict

from ..utils.json_utils import load_json, save_json


DEPARTMENTS_FILENAME = "departments.json"


def get_departments_path(config_dir: str) -> str:
    return os.path.join(config_dir, DEPARTMENTS_FILENAME)


def load_departments(config_dir: str) -> Dict[str, str]:
    """Загружает справочник подразделений. Ключ — код, значение — полное название."""
    path = get_departments_path(config_dir)
    data = load_json(path, {})
    # На всякий случай приводим к ожидаемому типу
    if not isinstance(data, dict):
        return {}
    return data


def save_departments(config_dir: str, departments: Dict[str, str]) -> None:
    """Сохраняет справочник подразделений."""
    path = get_departments_path(config_dir)
    save_json(path, departments)
