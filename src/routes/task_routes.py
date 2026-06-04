# -*- coding: utf-8 -*-
"""
REST-маршруты для блокнота задач (/api/tasks).
"""

import time
import os

from flask import Blueprint, request, jsonify

from ..config import Config
from ..models.tasks import (
    load_tasks,
    save_tasks,
    archive_completed_tasks,
    ensure_order_field,
)

task_bp = Blueprint('tasks', __name__)


def _get_config_dir():
    return os.path.join(Config.BASE_DIR, 'config')


@task_bp.route('/api/tasks', methods=['GET'])
def get_tasks():
    config_dir = _get_config_dir()
    tasks = load_tasks(config_dir)
    tasks = archive_completed_tasks(tasks)
    tasks = ensure_order_field(tasks)
    tasks.sort(key=lambda x: x.get('order', 0))
    save_tasks(config_dir, tasks)
    return jsonify(tasks)


@task_bp.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Текст задачи обязателен'}), 400

    config_dir = _get_config_dir()
    tasks = load_tasks(config_dir)
    tasks = ensure_order_field(tasks)

    # Сдвигаем все существующие задачи вниз (order + 1)
    for t in tasks:
        t['order'] = t.get('order', 0) + 1

    new_id = max([t.get('id', 0) for t in tasks]) + 1 if tasks else 1

    tasks.append({
        'id': new_id,
        'text': text,
        'status': 'active',
        'completed': False,
        'completed_at': None,
        'cancelled_comment': None,
        'cancelled_at': None,
        'created_at': time.time(),
        'order': 1,  # новая задача — наверх списка
    })
    save_tasks(config_dir, tasks)
    return jsonify({'success': True, 'task': tasks[-1]})


@task_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    config_dir = _get_config_dir()
    tasks = load_tasks(config_dir)

    for task in tasks:
        if task['id'] == task_id:
            if 'text' in data:
                task['text'] = data['text'].strip()
            if 'completed' in data:
                task['completed'] = data['completed']
                if data['completed']:
                    task['completed_at'] = time.time()
                else:
                    task['completed_at'] = None
                    task['status'] = 'active'
            if 'cancelled' in data and data['cancelled']:
                task['status'] = 'cancelled'
                task['cancelled_comment'] = data.get('comment', '')
                task['cancelled_at'] = time.time()
                task['completed'] = False
                task['completed_at'] = None
            break

    save_tasks(config_dir, tasks)
    return jsonify({'success': True, 'tasks': tasks})


@task_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    config_dir = _get_config_dir()
    tasks = load_tasks(config_dir)
    tasks = [t for t in tasks if t['id'] != task_id]
    save_tasks(config_dir, tasks)
    return jsonify({'success': True})


@task_bp.route('/api/tasks/<int:task_id>/move/<direction>', methods=['POST'])
def move_task(task_id, direction):
    if direction not in ('up', 'down'):
        return jsonify({'error': 'Неверное направление'}), 400

    config_dir = _get_config_dir()
    tasks = load_tasks(config_dir)
    ensure_order_field(tasks)

    idx = None
    for i, t in enumerate(tasks):
        if t['id'] == task_id:
            idx = i
            break

    if idx is None:
        return jsonify({'error': 'Задача не найдена'}), 404
    if direction == 'up' and idx == 0:
        return jsonify({'error': 'Задача уже вверху'}), 400
    if direction == 'down' and idx == len(tasks) - 1:
        return jsonify({'error': 'Задача уже внизу'}), 400

    other_idx = idx - 1 if direction == 'up' else idx + 1
    tasks[idx]['order'], tasks[other_idx]['order'] = (
        tasks[other_idx]['order'],
        tasks[idx]['order'],
    )
    tasks.sort(key=lambda x: x.get('order', 0))
    save_tasks(config_dir, tasks)
    return jsonify({'success': True})
