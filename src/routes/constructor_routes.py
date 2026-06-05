# -*- coding: utf-8 -*-
"""
REST-маршруты для Low-code Конструктора сводных таблиц:
- Загрузка Excel / выбор листа
- Просмотр данных с фильтрацией
- Построение сводной таблицы
- Скачивание результата
"""

import os
import uuid
import json
import logging
import traceback
import datetime as dt_m
from typing import Any
import numpy as np

import pandas as pd

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from ..config import Config
from ..services.constructor import (
    load_excel_file,
    load_sheet_data,
    _infer_column_types,
    _infer_column_types_from_df,
    _detect_header_row,
    apply_filters,
    build_pivot_table,
    save_pivot_to_xlsx,
    save_scenario,
    list_scenarios,
    load_scenario,
    delete_scenario,
    _ensure_scenarios_dir,
)
from ..utils.file_utils import safe_remove, read_file_to_df
from ..utils import sqlite_cache

logger = logging.getLogger(__name__)


def _sanitize_for_json(obj: Any) -> Any:
    """Рекурсивно преобразует любые не-JSON-типы (datetime, numpy, pandas и др.) в строки."""
    # --- datetime, date, time (в т.ч. pd.Timestamp — подкласс datetime) ---
    if isinstance(obj, (dt_m.datetime, dt_m.date, dt_m.time)):
        return str(obj)
    # --- numpy.datetime64 (НЕ является подклассом datetime.datetime!) ---
    if isinstance(obj, np.datetime64):
        return str(obj)
    # --- pandas.Timestamp (может не определяться через isinstance из-за версий) ---
    if hasattr(obj, 'strftime') and callable(obj.strftime):
        try:
            return str(obj)
        except Exception:
            pass
    # --- numpy целые ---
    if isinstance(obj, (np.integer,)):
        return int(obj)
    # --- numpy дробные (NaN → null) ---
    if isinstance(obj, (np.floating,)):
        if np.isnan(obj):
            return None
        return float(obj)
    # --- numpy bool ---
    if isinstance(obj, np.bool_):
        return bool(obj)
    # --- numpy массивы ---
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    # --- numpy строки (numpy.str_ — подкласс str, но на всякий случай) ---
    if isinstance(obj, np.str_):
        return str(obj)
    # --- bytes ---
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    # --- dict / list / tuple (рекурсия) ---
    if isinstance(obj, dict):
        # ВАЖНО: санитизируем и КЛЮЧИ тоже — они могут быть datetime из Excel-заголовков
        return {_sanitize_for_json(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    # --- Catch-all для любых других объектов, которые не сериализуются в JSON ---
    # Если у объекта есть метод __str__, используем его как строку
    # --- Python float может быть NaN (не сериализуется в JSON) ---
    if isinstance(obj, float):
        if obj != obj:  # NaN — единственное значение, не равное себе
            return None
        return obj
    if not isinstance(obj, (str, int, float, bool, type(None))):
        logger.debug('Catch-all _sanitize_for_json converts type=%s val=%r', type(obj).__name__, obj)
        return str(obj)
    return obj

constructor_bp = Blueprint('constructor', __name__)

# ---------------------------------------------------------------------------
# Persist-хранилище для загруженных файлов (file_id -> info)
# Хранится в config/constructor_temp_files.json, восстанавливается при старте
# ---------------------------------------------------------------------------
TEMP_FILES_JSON = os.path.join(Config.CONFIG_DIR, 'constructor_temp_files.json')


def _load_temp_files() -> dict:
    """Восстанавливает _temp_files из JSON-файла."""
    if not os.path.exists(TEMP_FILES_JSON):
        return {}
    try:
        with open(TEMP_FILES_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Фильтруем: удаляем записи, где файла на диске уже нет
        valid = {}
        for fid, info in data.items():
            path = info.get('path', '')
            if os.path.exists(path):
                valid[fid] = info
            else:
                logger.warning('Файл temp_file %s больше не существует на диске: %s', fid, path)
        return valid
    except Exception as e:
        logger.warning('Не удалось загрузить constructor_temp_files.json: %s', e)
        return {}


def _save_temp_files(temp_files: dict) -> None:
    """Сохраняет _temp_files в JSON-файл."""
    try:
        # Сохраняем только метаданные (без DataFrame)
        serializable = {}
        for fid, info in temp_files.items():
            serializable[fid] = {
                'path': info.get('path', ''),
                'filename': info.get('filename', ''),
            }
        os.makedirs(os.path.dirname(TEMP_FILES_JSON), exist_ok=True)
        with open(TEMP_FILES_JSON, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning('Не удалось сохранить constructor_temp_files.json: %s', e)


def _cfg(*parts):
    """Вспомогательная функция: возвращает путь к поддиректориям."""
    if not parts:
        return Config.USER_DATA_DIR
    first = parts[0]
    rest = parts[1:]
    if first == 'config':
        return os.path.join(Config.CONFIG_DIR, *rest)
    elif first == 'profiles':
        return os.path.join(Config.PROFILES_DIR, *rest)
    elif first == 'uploads':
        return os.path.join(Config.UPLOAD_DIR, *rest)
    return os.path.join(Config.BASE_DIR, *parts)


def _clean_orphan_uploads() -> None:
    """Удаляет файлы из uploads/, на которые нет ссылок в _temp_files."""
    upload_dir = _cfg('uploads')
    if not os.path.exists(upload_dir):
        return
    valid_paths = {info['path'] for info in _temp_files.values()}
    for fname in os.listdir(upload_dir):
        if fname.startswith('constructor_'):
            fpath = os.path.join(upload_dir, fname)
            if fpath not in valid_paths:
                try:
                    os.remove(fpath)
                except Exception:
                    pass


# Загружаем temp_files из JSON при старте модуля
_temp_files: dict = _load_temp_files()
_clean_orphan_uploads()


# ==================== 1. ЗАГРУЗКА EXCEL ====================

@constructor_bp.route('/api/constructor/upload', methods=['POST'])
def upload_excel():
    """
    Загружает Excel-файл, возвращает список листов и метаданные.
    Файл сохраняется временно для дальнейшей работы.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не загружен'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    # Проверка расширения
    filename = file.filename.lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls') or filename.endswith('.csv')):
        return jsonify({'error': 'Поддерживаются только файлы .xlsx, .xls и .csv'}), 400

    upload_dir = _cfg('uploads')
    os.makedirs(upload_dir, exist_ok=True)

    file_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename)
    temp_path = os.path.join(upload_dir, f'constructor_{file_id}_{safe_name}')
    file.save(temp_path)

    try:
        result = load_excel_file(temp_path)
        # Сохраняем в временном хранилище (persist)
        _temp_files[file_id] = {
            'path': temp_path,
            'filename': file.filename,
            'cached_df': None,  # для кэширования DataFrame
        }
        _save_temp_files(_temp_files)
        result['file_id'] = file_id
        result['filename'] = file.filename
        return jsonify(result)
    except Exception as e:
        safe_remove(temp_path)
        logger.error('Ошибка загрузки Excel в конструкторе: %s', e)
        return jsonify({'error': f'Ошибка чтения файла: {str(e)}'}), 500


# ==================== 2. ЗАГРУЗКА ДАННЫХ ЛИСТА ====================

@constructor_bp.route('/api/constructor/load', methods=['POST'])
def load_sheet():
    """
    Загружает метаданные указанного листа + сохраняет все данные в SQLite-кэш.
    Тело запроса: {file_id, sheet_name, header_row?, transpose?}
    header_row: номер строки с заголовками (0-based). None = автоопределение.
    transpose: если True — транспонировать данные.
    Возвращает: {columns, total_rows, dtypes, date_columns, header_row_used}

    ОПТИМИЗАЦИЯ: читаем Excel ОДИН раз, пишем в SQLite и строим ответ из
    того же DataFrame (раньше было два чтения — load_sheet_data + read_file_to_df).
    """
    data = request.get_json()
    file_id = data.get('file_id', '')
    sheet_name = data.get('sheet_name', '')
    header_row = data.get('header_row', None)  # может быть None (авто) или int
    transpose = data.get('transpose', False)   # транспонирование

    if not file_id or not sheet_name:
        return jsonify({'error': 'Не указаны file_id и sheet_name'}), 400

    file_info = _temp_files.get(file_id)
    if not file_info:
        return jsonify({'error': 'Файл не найден. Загрузите файл заново.'}), 404

    file_path = file_info['path']
    if not os.path.exists(file_path):
        return jsonify({'error': 'Файл не найден на диске. Загрузите заново.'}), 404

    try:
        # Автоопределение строки заголовков (читает только первые строки — быстро)
        if header_row is None:
            header_info = _detect_header_row(file_path, sheet_name)
            header_row = header_info['best_header_row']

        if transpose:
            # Транспонирование — сложная логика, используем старый путь
            result = load_sheet_data(
                file_path=file_path, sheet_name=sheet_name,
                limit=100, offset=0,
                header_row=header_row, transpose=True,
            )
            return jsonify(result)

        # ОПТИМИЗАЦИЯ: читаем все данные ОДИН раз
        full_df = read_file_to_df(file_path, sheet_name=sheet_name, header=header_row, dtype=str)
        full_df = full_df.fillna('').astype(str)

        # Сохраняем в SQLite-кэш
        try:
            cache_id = file_info.get('sqlite_cache_id')
            if not cache_id:
                cache_id = sqlite_cache.create_cache()
                file_info['sqlite_cache_id'] = cache_id
                _save_temp_files(_temp_files)

            sqlite_cache.save_dataframe(cache_id, full_df)
            logger.debug(
                "SQLite-кэш для file_id=%s: сохранено %d строк, cache_id=%s",
                file_id, len(full_df), cache_id
            )
        except Exception as cache_e:
            logger.warning("Не удалось создать SQLite-кэш для %s: %s", file_id, cache_e)

        # Строим ответ из тех же данных (без повторного чтения файла)
        columns = full_df.columns.tolist()
        total_rows = len(full_df)

        # Первые 100 строк для предпросмотра
        preview_df = full_df.head(100)
        data = preview_df.to_dict(orient='records')

        # Определяем типы колонок по DataFrame (не читая файл заново)
        dtypes = _infer_column_types_from_df(full_df, columns)
        date_columns = [col for col, dtype in dtypes.items() if dtype == 'date']

        result = {
            'columns': columns,
            'data': data,
            'total_rows': total_rows,
            'dtypes': dtypes,
            'date_columns': date_columns,
            'header_row_used': header_row,
        }
        return jsonify(result)
    except Exception as e:
        logger.error('Ошибка загрузки листа: %s\n%s', e, traceback.format_exc())
        return jsonify({'error': f'Ошибка загрузки листа: {str(e)}'}), 500


@constructor_bp.route('/api/constructor/detect_headers', methods=['POST'])
def detect_headers():
    """
    Определяет, где находятся заголовки в листе, и возвращает предпросмотр строк.
    Тело запроса: {file_id, sheet_name}
    Возвращает: {best_header_row, unnamed_ratio, needs_review, rows_preview: [...]}
    """
    data = request.get_json()
    file_id = data.get('file_id', '')
    sheet_name = data.get('sheet_name', '')

    if not file_id or not sheet_name:
        return jsonify({'error': 'Не указаны file_id и sheet_name'}), 400

    file_info = _temp_files.get(file_id)
    if not file_info:
        return jsonify({'error': 'Файл не найден. Загрузите файл заново.'}), 404

    file_path = file_info['path']
    if not os.path.exists(file_path):
        return jsonify({'error': 'Файл не найден на диске. Загрузите заново.'}), 404

    try:
        result = _detect_header_row(file_path, sheet_name)
        return jsonify(result)
    except Exception as e:
        logger.error('Ошибка определения заголовков: %s', e)
        return jsonify({'error': f'Ошибка определения заголовков: {str(e)}'}), 500


# ==================== 3. ПРЕДПРОСМОТР С ФИЛЬТРАЦИЕЙ ====================

@constructor_bp.route('/api/constructor/preview', methods=['POST'])
def preview_data():
    """
    Применяет фильтры и возвращает данные.
    Тело запроса: {file_id, sheet_name, selected_columns?, filters?, sort_column?, sort_order?, limit?, offset?, header_row?}
    """
    data = request.get_json()
    file_id = data.get('file_id', '')
    sheet_name = data.get('sheet_name', '')
    selected_columns = data.get('selected_columns', None)
    filters = data.get('filters', None)
    sort_column = data.get('sort_column', None)
    sort_order = data.get('sort_order', 'asc')
    limit = int(data.get('limit', 100))
    offset = int(data.get('offset', 0))
    header_row = int(data.get('header_row', 0))

    if not file_id or not sheet_name:
        return jsonify({'error': 'Не указаны file_id и sheet_name'}), 400

    file_info = _temp_files.get(file_id)
    if not file_info:
        return jsonify({'error': 'Файл не найден'}), 404

    file_path = file_info['path']
    if not os.path.exists(file_path):
        return jsonify({'error': 'Файл не найден на диске'}), 404

    try:
        cache_id = file_info.get('sqlite_cache_id')
        if cache_id:
            # Используем SQLite-кэш (быстрый путь)
            try:
                preview_data_sqlite, preview_columns, total_filtered = sqlite_cache.query_data(
                    cache_id,
                    selected_columns=selected_columns,
                    filters=filters,
                    sort_column=sort_column,
                    sort_order=sort_order,
                    limit=limit,
                    offset=offset,
                )
                total_rows = sqlite_cache.get_row_count(cache_id)
                result = {
                    'columns': preview_columns,
                    'data': preview_data_sqlite,
                    'total_rows': total_rows,
                    'filtered_count': total_filtered,
                }
                return jsonify(_sanitize_for_json(result))
            except Exception as sqlite_e:
                logger.warning("SQLite-кэш недоступен, падаем на Excel: %s", sqlite_e)
                # Падаем через apply_filters ниже

        # Резервный путь: читаем из Excel через apply_filters
        cached_df = file_info.get('cached_df')
        result = apply_filters(
            file_path, sheet_name,
            selected_columns=selected_columns,
            filters=filters,
            sort_column=sort_column,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
            cached_df=cached_df,
            header_row=header_row,
        )
        return jsonify(_sanitize_for_json(result))
    except Exception as e:
        logger.error('Ошибка предпросмотра: %s\n%s', e, traceback.format_exc())
        return jsonify({'error': f'Ошибка предпросмотра: {str(e)}'}), 500


# ==================== 4. СВОДНАЯ ТАБЛИЦА ====================

@constructor_bp.route('/api/constructor/pivot', methods=['POST'])
def pivot_table():
    """
    Строит сводную таблицу с поддержкой множественных агрегаций.
    Тело запроса: {
        file_id, sheet_name,
        rows: [...], values: [...], cols?: [...],
        agg_functions?: ['sum'|'mean'|'count'|'min'|'max'|'none', ...],
        output_format?: 'flat'|'hierarchical',
        filters?: {...},
        totals_mode?: 'none'|'rows'|'cols'|'both'
    }
    """
    data = request.get_json()
    file_id = data.get('file_id', '')
    sheet_name = data.get('sheet_name', '')
    rows = data.get('rows', [])
    values = data.get('values', [])
    cols = data.get('cols', None)
    agg_functions = data.get('agg_functions', ['sum'])
    output_format = data.get('output_format', 'flat')
    filters = data.get('filters', None)
    selected_columns = data.get('selected_columns', None)
    totals_mode = data.get('totals_mode', 'none')

    if not file_id or not sheet_name:
        return jsonify({'error': 'Не указаны file_id и sheet_name'}), 400

    if not rows or not values:
        return jsonify({'error': 'Укажите строки (rows) и значения (values) для сводной таблицы'}), 400

    if not agg_functions or len(agg_functions) == 0:
        return jsonify({'error': 'Укажите хотя бы одну функцию агрегации'}), 400

    file_info = _temp_files.get(file_id)
    if not file_info:
        return jsonify({'error': 'Файл не найден'}), 404

    file_path = file_info['path']
    if not os.path.exists(file_path):
        return jsonify({'error': 'Файл не найден на диске'}), 404

    header_row = int(data.get('header_row', 0))

    try:
        # Пробуем использовать SQLite-кэш
        cache_id = file_info.get('sqlite_cache_id')
        cached_df = file_info.get('cached_df')

        if cache_id and cached_df is None:
            # Загружаем DataFrame из SQLite (если ещё не в памяти)
            try:
                cached_df = sqlite_cache.load_full_dataframe(cache_id)
                file_info['cached_df'] = cached_df
            except Exception as sqlite_e:
                logger.warning("SQLite-кэш недоступен для pivot: %s", sqlite_e)

        result = build_pivot_table(
            file_path, sheet_name,
            rows=rows,
            values=values,
            cols=cols,
            agg_functions=agg_functions,
            filters=filters,
            selected_columns=selected_columns,
            output_format=output_format,
            cached_df=cached_df,
            totals_mode=totals_mode,
            header_row=header_row,
        )
        return jsonify(_sanitize_for_json(result))
    except Exception as e:
        logger.error('Ошибка построения сводной: %s\n%s', e, traceback.format_exc())
        return jsonify({'error': f'Ошибка построения сводной таблицы: {str(e)}'}), 500


# ==================== 5. СКАЧИВАНИЕ РЕЗУЛЬТАТА ====================

@constructor_bp.route('/api/constructor/download', methods=['POST'])
def download_result():
    """
    Сохраняет сводную таблицу в XLSX и возвращает file_id для скачивания.
    Тело запроса: {pivot_data, columns, filename?, row_columns?}
    """
    data = request.get_json()
    pivot_data = data.get('pivot_data', [])
    columns = data.get('columns', [])
    filename = data.get('filename', 'сводная_таблица.xlsx')
    row_columns = data.get('row_columns', None)

    if not pivot_data or not columns:
        return jsonify({'error': 'Нет данных для выгрузки'}), 400

    upload_dir = _cfg('uploads')
    os.makedirs(upload_dir, exist_ok=True)

    file_id = uuid.uuid4().hex
    output_path = os.path.join(upload_dir, f'temp_result_{file_id}.xlsx')

    try:
        save_pivot_to_xlsx(pivot_data, columns, output_path, row_columns=row_columns)
        return jsonify({
            'file_id': file_id,
            'filename': filename,
            'download_url': f'/convert/download_temp/{file_id}',
        })
    except Exception as e:
        logger.error('Ошибка сохранения XLSX: %s', e)
        return jsonify({'error': f'Ошибка сохранения: {str(e)}'}), 500


# ==================== 6. СЦЕНАРИИ (СОХРАНЕНИЕ НАСТРОЕК) ====================

@constructor_bp.route('/api/constructor/scenario/save', methods=['POST'])
def api_save_scenario():
    """
    Сохраняет сценарий конструктора.
    Тело запроса: {name, params}
    """
    data = request.get_json()
    name = data.get('name', '').strip()
    params = data.get('params', {})

    if not name:
        return jsonify({'error': 'Укажите название сценария'}), 400
    if not params:
        return jsonify({'error': 'Нет параметров для сохранения'}), 400

    try:
        _ensure_scenarios_dir()
        result = save_scenario(name, params)
        return jsonify(result)
    except Exception as e:
        logger.error('Ошибка сохранения сценария: %s', e)
        return jsonify({'error': f'Ошибка сохранения сценария: {str(e)}'}), 500


@constructor_bp.route('/api/constructor/scenarios', methods=['GET'])
def api_list_scenarios():
    """Возвращает список сохранённых сценариев."""
    try:
        _ensure_scenarios_dir()
        scenarios = list_scenarios()
        return jsonify({'scenarios': scenarios})
    except Exception as e:
        logger.error('Ошибка получения списка сценариев: %s', e)
        return jsonify({'error': f'Ошибка загрузки сценариев: {str(e)}'}), 500


@constructor_bp.route('/api/constructor/scenario/load', methods=['POST'])
def api_load_scenario():
    """
    Загружает сценарий по имени.
    Тело запроса: {name}
    """
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Укажите название сценария'}), 400

    try:
        _ensure_scenarios_dir()
        scenario = load_scenario(name)
        if scenario is None:
            return jsonify({'error': f'Сценарий "{name}" не найден'}), 404
        return jsonify(scenario)
    except Exception as e:
        logger.error('Ошибка загрузки сценария: %s', e)
        return jsonify({'error': f'Ошибка загрузки сценария: {str(e)}'}), 500


@constructor_bp.route('/api/constructor/scenario/delete', methods=['POST'])
def api_delete_scenario():
    """
    Удаляет сценарий по имени.
    Тело запроса: {name}
    """
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Укажите название сценария'}), 400

    try:
        _ensure_scenarios_dir()
        success = delete_scenario(name)
        if not success:
            return jsonify({'error': f'Сценарий "{name}" не найден'}), 404
        return jsonify({'success': True, 'message': f'Сценарий "{name}" удалён'})
    except Exception as e:
        logger.error('Ошибка удаления сценария: %s', e)
        return jsonify({'error': f'Ошибка удаления сценария: {str(e)}'}), 500


# ==================== 7. ПОЛУЧЕНИЕ ИНФОРМАЦИИ О ФАЙЛЕ ====================

@constructor_bp.route('/api/constructor/file_info', methods=['POST'])
def get_file_info():
    """Возвращает информацию о загруженном файле."""
    data = request.get_json()
    file_id = data.get('file_id', '')
    if not file_id:
        return jsonify({'error': 'Не указан file_id'}), 400

    file_info = _temp_files.get(file_id)
    if not file_info:
        return jsonify({'error': 'Файл не найден'}), 404

    return jsonify({
        'file_id': file_id,
        'filename': file_info.get('filename', ''),
        'exists': os.path.exists(file_info['path']),
    })


# ==================== 8. ЗАКРЫТИЕ ФАЙЛА (ОЧИСТКА) ====================

@constructor_bp.route('/api/constructor/close', methods=['POST'])
def close_file():
    """Удаляет временный файл из хранилища."""
    data = request.get_json()
    file_id = data.get('file_id', '')
    if not file_id:
        return jsonify({'error': 'Не указан file_id'}), 400

    file_info = _temp_files.pop(file_id, None)
    if file_info:
        # Очищаем SQLite-кэш
        sqlite_cache_id = file_info.get('sqlite_cache_id')
        if sqlite_cache_id:
            sqlite_cache.delete_cache(sqlite_cache_id)
        # Очищаем кэш DataFrame, если был
        if 'cached_df' in file_info:
            file_info['cached_df'] = None
        safe_remove(file_info['path'])
        _save_temp_files(_temp_files)
        return jsonify({'success': True, 'message': 'Файл удалён'})

    return jsonify({'error': 'Файл не найден'}), 404
