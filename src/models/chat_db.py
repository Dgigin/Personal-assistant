# -*- coding: utf-8 -*-
"""
Модель для работы с историей чатов DeepSeek (SQLite).
"""

import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional


DB_FILENAME = "chat_history.db"


def get_db_path(config_dir: str) -> str:
    import os
    return os.path.join(config_dir, DB_FILENAME)


def init_db(config_dir: str) -> None:
    """Создаёт таблицы для хранения диалогов и сообщений."""
    db_path = get_db_path(config_dir)
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
        ''')
        conn.commit()


def get_conversations(config_dir: str) -> List[Dict[str, Any]]:
    """Возвращает все диалоги, отсортированные по дате обновления (сначала новые)."""
    db_path = get_db_path(config_dir)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT * FROM conversations ORDER BY updated_at DESC'
        ).fetchall()
        return [dict(row) for row in rows]


def create_conversation(config_dir: str, title: str = "Новый диалог") -> Dict[str, str]:
    """Создаёт новый диалог и возвращает его id и title."""
    conv_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db_path = get_db_path(config_dir)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)',
            (conv_id, title, now, now)
        )
    return {"id": conv_id, "title": title}


def get_messages(config_dir: str, conversation_id: str) -> List[Dict[str, str]]:
    """Возвращает список сообщений для указанного диалога."""
    db_path = get_db_path(config_dir)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id',
            (conversation_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def add_message(config_dir: str, conversation_id: str, role: str, content: str) -> None:
    """Добавляет сообщение в диалог и обновляет updated_at."""
    now = datetime.now().isoformat()
    db_path = get_db_path(config_dir)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)',
            (conversation_id, role, content, now)
        )
        conn.execute(
            'UPDATE conversations SET updated_at = ? WHERE id = ?',
            (now, conversation_id)
        )
        conn.commit()


def delete_conversation(config_dir: str, conversation_id: str) -> None:
    """Удаляет диалог и все его сообщения."""
    db_path = get_db_path(config_dir)
    with sqlite3.connect(db_path) as conn:
        conn.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
        conn.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
        conn.commit()


def rename_conversation(config_dir: str, conversation_id: str, new_title: str) -> None:
    """Переименовывает диалог."""
    db_path = get_db_path(config_dir)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'UPDATE conversations SET title = ? WHERE id = ?',
            (new_title, conversation_id)
        )
        conn.commit()
