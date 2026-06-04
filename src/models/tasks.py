# -*- coding: utf-8 -*-
"""
Модель для работы с блокнотом задач (tasks.json).
"""

import os
import time
from typing import List, Dict, Any, Optional

from ..utils.json_utils import load_json, save_json


TASKS_FILENAME = "tasks.json"


# Константы статусов
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUS_CANCELLED = "cancelled"

# Время в секундах, через которое выполненная задача архивируется
ARCHIVE_AFTER_SECONDS = 3600  # 1 час


def get_tasks_path(config_dir: str) -> str:
    return os.path.join(config_dir, TASKS_FILENAME)


def load_tasks(config_dir: str) -> List[Dict[str, Any]]:
    """Загружает список задач."""
    path = get_tasks_path(config_dir)
    data = load_json(path, [])
    if not isinstance(data, list):
        return []
    return data


def save_tasks(config_dir: str, tasks: List[Dict[str, Any]]) -> None:
    """Сохраняет список задач."""
    path = get_tasks_path(config_dir)
    save_json(path, tasks)


def archive_completed_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Переводит выполненные задачи в статус 'archived' через 24 часа."""
    now = time.time()
    for task in tasks:
        if task.get('status') == STATUS_ACTIVE and task.get('completed', False):
            completed_at = task.get('completed_at', 0)
            if completed_at and (now - completed_at) >= ARCHIVE_AFTER_SECONDS:
                task['status'] = STATUS_ARCHIVED
    return tasks


def get_max_order(tasks: List[Dict[str, Any]]) -> int:
    """Возвращает максимальное значение order среди задач."""
    orders = [t.get('order', 0) for t in tasks]
    return max(orders) if orders else 0


def ensure_order_field(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Добавляет недостающие поля (order, cancelled_at), если их нет."""
    for i, t in enumerate(tasks):
        if 'order' not in t:
            t['order'] = i + 1
        if 'cancelled_at' not in t:
            t['cancelled_at'] = None
    return tasks
