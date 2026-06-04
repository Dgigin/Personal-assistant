# -*- coding: utf-8 -*-
"""
Модель для работы с профилями маппинга (profiles/<имя>.json).

Структура профиля:
{
    "name": "Имя профиля",
    "created_at": "2024-01-01T12:00:00",
    "mapping": [
        {
            "source_column": "Столбец1",
            "default_period": 30,
            "budget": "...",
            "target_article": "..."
        }
    ]
}
"""

import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from ..utils.file_utils import safe_filename
from ..utils.json_utils import load_json, save_json


PROFILES_DIRNAME = "profiles"


def get_profiles_dir(base_dir: str) -> str:
    return os.path.join(base_dir, PROFILES_DIRNAME)


def get_profile_path(profiles_dir: str, profile_name: str) -> str:
    return os.path.join(profiles_dir, f"{safe_filename(profile_name)}.json")


def load_profile(profiles_dir: str, profile_name: str) -> Optional[Dict[str, Any]]:
    """Загружает профиль маппинга. Возвращает None, если профиль не найден."""
    path = get_profile_path(profiles_dir, profile_name)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_profile(
    profiles_dir: str,
    profile_name: str,
    mapping: List[Dict[str, Any]],
    created_at: Optional[str] = None,
) -> None:
    """Сохраняет или перезаписывает профиль маппинга."""
    profile = {
        "name": profile_name,
        "created_at": created_at or datetime.now().isoformat(),
        "mapping": mapping,
    }
    path = get_profile_path(profiles_dir, profile_name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def list_profiles(profiles_dir: str) -> List[str]:
    """Возвращает список имён всех профилей."""
    profiles = []
    if not os.path.exists(profiles_dir):
        return profiles
    for fname in os.listdir(profiles_dir):
        if fname.endswith('.json'):
            path = os.path.join(profiles_dir, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    profiles.append(data.get('name', fname[:-5]))
            except Exception as e:
                logger.warning('Не удалось прочитать профиль %s: %s', fname, e)
                profiles.append(fname[:-5])
    return profiles


def delete_profile(profiles_dir: str, profile_name: str) -> bool:
    """Удаляет профиль. Возвращает True, если удаление прошло успешно."""
    path = get_profile_path(profiles_dir, profile_name)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
