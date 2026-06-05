# -*- coding: utf-8 -*-
"""
SQLite-кеш для быстрой работы с данными Excel.
Позволяет избежать повторного чтения Excel-файла при каждом запросе.

Архитектура:
  1. При загрузке листа (load_sheet) — все данные пишутся в SQLite
  2. Все последующие операции (preview, pivot) читают из SQLite
  3. При закрытии файла — SQLite-файл удаляется
"""

import os
import sqlite3
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Папка для SQLite-кэша
SQLITE_CACHE_DIR = None  # инициализируется при первом вызове


def _get_cache_dir() -> str:
    """Возвращает путь к папке для SQLite-кэша, создавая её при необходимости."""
    global SQLITE_CACHE_DIR
    if SQLITE_CACHE_DIR is None:
        # Используем uploads папку рядом с config
        from flask import current_app
        SQLITE_CACHE_DIR = os.path.join(current_app.root_path, '..', 'config', 'sqlite_cache')
    os.makedirs(SQLITE_CACHE_DIR, exist_ok=True)
    return SQLITE_CACHE_DIR


def _get_db_path(cache_id: str) -> str:
    """Возвращает полный путь к SQLite-файлу по cache_id."""
    return os.path.join(_get_cache_dir(), f"{cache_id}.db")


def create_cache() -> str:
    """
    Создаёт новый SQLite-кэш и возвращает его ID.

    :return: Уникальный cache_id
    """
    cache_id = uuid.uuid4().hex
    db_path = _get_db_path(cache_id)
    # Просто создаём пустой файл БД
    conn = sqlite3.connect(db_path)
    conn.close()
    logger.debug("Создан SQLite-кэш: %s", db_path)
    return cache_id


def save_dataframe(cache_id: str, df: pd.DataFrame, table_name: str = 'data') -> int:
    """
    Сохраняет DataFrame в SQLite-таблицу.

    :param cache_id: ID кэша
    :param df: DataFrame для сохранения
    :param table_name: Имя таблицы (по умолчанию 'data')
    :return: Количество сохранённых строк
    """
    db_path = _get_db_path(cache_id)
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite-кэш не найден: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        # Сохраняем все данные как текст (для совместимости с JSON-сериализацией)
        df_str = df.astype(str)
        df_str.to_sql(table_name, conn, if_exists='replace', index=False)
        count = len(df_str)
        logger.debug("Сохранено %d строк в SQLite-кэш %s, таблица %s", count, cache_id, table_name)
        return count
    finally:
        conn.close()


def get_columns(cache_id: str, table_name: str = 'data') -> List[str]:
    """
    Возвращает список колонок таблицы.

    :param cache_id: ID кэша
    :param table_name: Имя таблицы
    :return: Список имён колонок
    """
    db_path = _get_db_path(cache_id)
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite-кэш не найден: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(f"SELECT * FROM [{table_name}] LIMIT 0")
        return [desc[0] for desc in cursor.description]
    finally:
        conn.close()


def get_row_count(cache_id: str, table_name: str = 'data') -> int:
    """
    Возвращает общее количество строк в таблице.

    :param cache_id: ID кэша
    :param table_name: Имя таблицы
    :return: Количество строк
    """
    db_path = _get_db_path(cache_id)
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite-кэш не найден: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def query_data(
    cache_id: str,
    selected_columns: Optional[List[str]] = None,
    filters: Optional[Dict[str, Dict[str, Any]]] = None,
    sort_column: Optional[str] = None,
    sort_order: str = 'asc',
    limit: int = 100,
    offset: int = 0,
    table_name: str = 'data',
) -> Tuple[List[Dict[str, Any]], List[str], int]:
    """
    Выполняет запрос к SQLite-кэшу с фильтрацией, сортировкой и пагинацией.

    :param cache_id: ID кэша
    :param selected_columns: Список колонок для выборки (None = все)
    :param filters: Словарь фильтров {column: {type, value}}
    :param sort_column: Колонка для сортировки
    :param sort_order: 'asc' или 'desc'
    :param limit: Макс. количество строк
    :param offset: Смещение
    :param table_name: Имя таблицы
    :return: (data, columns, total_rows)
    """
    db_path = _get_db_path(cache_id)
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite-кэш не найден: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Получаем все колонки таблицы
        all_columns = get_columns(cache_id, table_name)

        # Определяем, какие колонки выбираем
        if selected_columns and len(selected_columns) > 0:
            valid_cols = [c for c in selected_columns if c in all_columns]
            if not valid_cols:
                valid_cols = all_columns
        else:
            valid_cols = all_columns

        col_names = ', '.join(f'"[{c}]"' for c in valid_cols)

        # Строим WHERE из фильтров
        where_clauses = []
        params = []
        if filters:
            for col, filter_def in filters.items():
                if col not in all_columns:
                    continue
                filter_type = filter_def.get('type', '')
                filter_value = filter_def.get('value', '')

                if filter_type == 'equals' and filter_value != '':
                    where_clauses.append(f'LOWER("[{col}]") = LOWER(?)')
                    params.append(filter_value)
                elif filter_type == 'contains' and filter_value != '':
                    where_clauses.append(f'LOWER("[{col}]") LIKE LOWER(?)')
                    params.append(f'%{filter_value}%')
                elif filter_type == 'not_equals' and filter_value != '':
                    where_clauses.append(f'LOWER("[{col}]") != LOWER(?)')
                    params.append(filter_value)
                elif filter_type == 'greater_than' and filter_value != '':
                    where_clauses.append(f'CAST("[{col}]" AS REAL) > ?')
                    params.append(float(filter_value))
                elif filter_type == 'less_than' and filter_value != '':
                    where_clauses.append(f'CAST("[{col}]" AS REAL) < ?')
                    params.append(float(filter_value))
                elif filter_type == 'is_empty':
                    where_clauses.append(f'("[{col}]" = \'\' OR "[{col}]" IS NULL)')
                elif filter_type == 'is_not_empty':
                    where_clauses.append(f'("[{col}]" != \'\' AND "[{col}]" IS NOT NULL)')

        where_sql = ''
        if where_clauses:
            where_sql = ' WHERE ' + ' AND '.join(where_clauses)

        # Подсчитываем общее количество отфильтрованных строк
        count_sql = f'SELECT COUNT(*) FROM [{table_name}]{where_sql}'
        cursor = conn.execute(count_sql, params)
        total_filtered = cursor.fetchone()[0]

        # Сортировка
        order_sql = ''
        if sort_column and sort_column in all_columns:
            direction = 'ASC' if sort_order == 'asc' else 'DESC'
            order_sql = f' ORDER BY "[{sort_column}]" {direction}'

        # Пагинация
        limit_sql = f' LIMIT {limit} OFFSET {offset}'

        # Финальный запрос
        query = f'SELECT {col_names} FROM [{table_name}]{where_sql}{order_sql}{limit_sql}'
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        data = [dict(row) for row in rows]
        return data, valid_cols, total_filtered
    finally:
        conn.close()


def load_full_dataframe(cache_id: str, table_name: str = 'data') -> pd.DataFrame:
    """
    Загружает все данные из SQLite-кэша в pandas DataFrame.

    :param cache_id: ID кэша
    :param table_name: Имя таблицы
    :return: DataFrame со всеми данными
    """
    db_path = _get_db_path(cache_id)
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite-кэш не найден: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql(f'SELECT * FROM [{table_name}]', conn)
        return df
    finally:
        conn.close()


def delete_cache(cache_id: str) -> None:
    """
    Удаляет SQLite-кэш.

    :param cache_id: ID кэша
    """
    if not cache_id:
        return
    db_path = _get_db_path(cache_id)
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.debug("Удалён SQLite-кэш: %s", db_path)
    except Exception as e:
        logger.warning("Ошибка удаления SQLite-кэша %s: %s", db_path, e)
