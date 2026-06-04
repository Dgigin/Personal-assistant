# -*- coding: utf-8 -*-
"""
Общие утилиты для загрузки/сохранения JSON-файлов.
"""

import os
import json
from typing import Any, Dict, List, Union


JSONData = Union[Dict[str, Any], List[Any]]


def load_json(filepath: str, default: JSONData = None) -> JSONData:
    """Загружает JSON из файла. Если файла нет — возвращает default."""
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath: str, data: JSONData) -> None:
    """Сохраняет данные в JSON-файл с отступами и UTF-8."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
