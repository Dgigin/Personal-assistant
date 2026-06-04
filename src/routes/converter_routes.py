# -*- coding: utf-8 -*-
"""
REST-маршруты для конвертера Excel:
- Справочник подразделений (/api/departments)
- Справочник статей расходов (/api/expense_articles)
- Профили маппинга (/api/profiles)
- Конвертация: статистика, предпросмотр, скачивание (/convert/*)
"""

import json
import os
import uuid

from flask import Blueprint, request, jsonify, send_file
import pandas as pd
from werkzeug.utils import secure_filename

from ..config import Config
from ..models.departments import load_departments, save_departments
from ..models.expense_articles import load_expense_articles, save_expense_articles
from ..models.profiles import load_profile, save_profile, list_profiles, delete_profile
from ..services.converter import transform_excel_with_mapping
from ..utils.file_utils import safe_remove, generate_temp_path

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
converter_bp = Blueprint('converter', __name__)


def _cfg(*parts):
    """Вспомогательная функция: возвращает путь от Config.BASE_DIR."""
    return os.path.join(Config.BASE_DIR, *parts)


# ==================== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ====================

def _parse_conversion_request(request):
    """
    Извлекает и парсит общие параметры для convert-маршрутов (stats, preview, download).

    Возвращает dict с ключами:
        file, profile, dept_config, articles_config, mapping,
        start_date, period_overrides, ignore_depts, input_path
    или вызывает jsonify(...) с кодом ошибки в случае проблем.
    """
    if 'file' not in request.files:
        return {'error': ('Файл не загружен', 400)}
    file = request.files['file']
    if file.filename == '':
        return {'error': ('Файл не выбран', 400)}

    profile_name = request.form.get('profile_name', '')
    if not profile_name:
        return {'error': ('Не указан профиль', 400)}

    start_date = request.form.get('start_date', '')

    # Парсинг периодов
    periods_json = request.form.get('periods', '{}')
    try:
        period_overrides = json.loads(periods_json)
    except Exception:
        period_overrides = {}

    # Парсинг игнорируемых подразделений
    ignore_depts_json = request.form.get('ignored_depts', '[]')
    try:
        ignore_depts = json.loads(ignore_depts_json)
    except Exception:
        ignore_depts = []

    config_dir = _cfg('config')
    profiles_dir = _cfg('profiles')
    upload_dir = _cfg('uploads')

    profile = load_profile(profiles_dir, profile_name)
    if not profile:
        return {'error': (f'Профиль "{profile_name}" не найден', 404)}

    dept_config = load_departments(config_dir)
    articles_config = load_expense_articles(config_dir)
    mapping = profile['mapping']

    filename = secure_filename(file.filename)
    input_path = os.path.join(upload_dir, filename)
    file.save(input_path)

    return {
        'input_path': input_path,
        'mapping': mapping,
        'dept_config': dept_config,
        'articles_config': articles_config,
        'start_date': start_date,
        'period_overrides': period_overrides,
        'ignore_depts': ignore_depts,
        'config_dir': config_dir,
        'upload_dir': upload_dir,
    }


# ==================== 1. ПОДРАЗДЕЛЕНИЯ ====================

@converter_bp.route('/api/departments', methods=['GET'])
def get_departments():
    return jsonify(load_departments(_cfg('config')))


@converter_bp.route('/api/departments', methods=['POST'])
def add_department():
    data = request.get_json()
    code = data.get('code', '').strip()
    name = data.get('name', '').strip()
    if not code or not name:
        return jsonify({'error': 'Код и наименование обязательны'}), 400
    config_dir = _cfg('config')
    depts = load_departments(config_dir)
    if code in depts:
        return jsonify({'error': 'Такой код уже существует'}), 400
    depts[code] = name
    save_departments(config_dir, depts)
    return jsonify({'success': True, 'departments': depts})


@converter_bp.route('/api/departments/<code>', methods=['PUT'])
def update_department(code):
    data = request.get_json()
    new_code = data.get('code', '').strip()
    new_name = data.get('name', '').strip()
    if not new_code or not new_name:
        return jsonify({'error': 'Код и наименование обязательны'}), 400
    config_dir = _cfg('config')
    depts = load_departments(config_dir)
    if code not in depts:
        return jsonify({'error': 'Подразделение не найдено'}), 404
    if new_code != code and new_code in depts:
        return jsonify({'error': f'Код "{new_code}" уже существует'}), 400
    del depts[code]
    depts[new_code] = new_name
    save_departments(config_dir, depts)
    return jsonify({'success': True, 'departments': depts})


@converter_bp.route('/api/departments/<code>', methods=['DELETE'])
def delete_department(code):
    config_dir = _cfg('config')
    depts = load_departments(config_dir)
    if code not in depts:
        return jsonify({'error': 'Подразделение не найдено'}), 404
    del depts[code]
    save_departments(config_dir, depts)
    return jsonify({'success': True, 'departments': depts})


# ==================== 2. СТАТЬИ РАСХОДОВ ====================

@converter_bp.route('/api/expense_articles', methods=['GET'])
def get_expense_articles():
    return jsonify(load_expense_articles(_cfg('config')))


@converter_bp.route('/api/expense_articles', methods=['POST'])
def add_expense_article():
    data = request.get_json()
    code = data.get('code', '').strip()
    name = data.get('name', '').strip()
    budget = data.get('budget', '').strip()
    if not code or not name or not budget:
        return jsonify({'error': 'Код, наименование и бюджет обязательны'}), 400
    config_dir = _cfg('config')
    arts = load_expense_articles(config_dir)
    if code in arts:
        return jsonify({'error': 'Такой код уже существует'}), 400
    arts[code] = {'name': name, 'budget': budget}
    save_expense_articles(config_dir, arts)
    return jsonify({'success': True, 'articles': arts})


@converter_bp.route('/api/expense_articles/<code>', methods=['PUT'])
def update_expense_article(code):
    data = request.get_json()
    new_code = data.get('code', '').strip()
    new_name = data.get('name', '').strip()
    new_budget = data.get('budget', '').strip()
    if not new_code or not new_name or not new_budget:
        return jsonify({'error': 'Код, наименование и бюджет обязательны'}), 400
    config_dir = _cfg('config')
    arts = load_expense_articles(config_dir)
    if code not in arts:
        return jsonify({'error': 'Статья не найдена'}), 404
    if new_code != code and new_code in arts:
        return jsonify({'error': f'Код "{new_code}" уже существует'}), 400
    del arts[code]
    arts[new_code] = {'name': new_name, 'budget': new_budget}
    save_expense_articles(config_dir, arts)
    return jsonify({'success': True, 'articles': arts})


@converter_bp.route('/api/expense_articles/<code>', methods=['DELETE'])
def delete_expense_article(code):
    config_dir = _cfg('config')
    arts = load_expense_articles(config_dir)
    if code not in arts:
        return jsonify({'error': 'Статья не найдена'}), 404
    del arts[code]
    save_expense_articles(config_dir, arts)
    return jsonify({'success': True, 'articles': arts})


# ==================== 3. ПРОФИЛИ ====================

@converter_bp.route('/api/profiles', methods=['GET'])
def api_list_profiles():
    return jsonify(list_profiles(_cfg('profiles')))


@converter_bp.route('/api/profiles/<profile_name>', methods=['GET'])
def api_get_profile(profile_name):
    profiles_dir = _cfg('profiles')
    profile = load_profile(profiles_dir, profile_name)
    if not profile:
        return jsonify({'error': 'Профиль не найден'}), 404
    return jsonify(profile)


@converter_bp.route('/api/profiles', methods=['POST'])
def api_save_profile():
    data = request.get_json()
    name = data.get('name', '').strip()
    mapping = data.get('mapping', [])
    if not name or not mapping:
        return jsonify({'error': 'Имя и маппинг обязательны'}), 400
    for rule in mapping:
        if 'source_column' not in rule or 'default_period' not in rule:
            return jsonify({'error': 'Каждое правило должно содержать source_column и default_period'}), 400
        if 'budget' not in rule:
            rule['budget'] = ''
        if 'target_article' not in rule:
            rule['target_article'] = ''
    save_profile(_cfg('profiles'), name, mapping)
    return jsonify({'success': True, 'name': name})


@converter_bp.route('/api/profiles/<profile_name>', methods=['DELETE'])
def api_delete_profile(profile_name):
    if delete_profile(_cfg('profiles'), profile_name):
        return jsonify({'success': True})
    return jsonify({'error': 'Профиль не найден'}), 404


# ==================== 4. ПОЛУЧЕНИЕ СТОЛБЦОВ ФАЙЛА ====================

@converter_bp.route('/api/columns', methods=['POST'])
def get_file_columns():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не загружен'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    upload_dir = _cfg('uploads')
    filename = secure_filename(file.filename)
    temp_path = os.path.join(upload_dir, f"temp_{uuid.uuid4().hex}.xlsx")
    file.save(temp_path)

    try:
        df = pd.read_excel(temp_path, sheet_name=0, nrows=0)
        columns = df.columns.tolist()
        if len(columns) < 1:
            return jsonify({'error': 'Файл не содержит столбцов'}), 400
        columns = columns[1:]  # первый столбец — подразделения (не маппится)
        return jsonify({'columns': columns})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        safe_remove(temp_path)


# ==================== 5. КОНВЕРТАЦИЯ ====================

@converter_bp.route('/convert/stats', methods=['POST'])
def convert_stats():
    parsed = _parse_conversion_request(request)
    if 'error' in parsed:
        return jsonify({'error': parsed['error'][0]}), parsed['error'][1]

    try:
        df, unknown_depts, unknown_articles = transform_excel_with_mapping(
            parsed['input_path'],
            parsed['mapping'],
            parsed['dept_config'],
            parsed['articles_config'],
            parsed['start_date'],
            parsed['period_overrides'],
            parsed['ignore_depts'],
        )
        stats = {
            'unique_departments': df['Подразделение'].nunique() if not df.empty else 0,
            'total_limits_count': len(df),
            'total_limit_sum': float(df['Лимит'].sum()) if not df.empty else 0.0,
            'unknown_departments': unknown_depts,
            'unknown_articles': unknown_articles,
        }
        return jsonify({'stats': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        safe_remove(parsed['input_path'])


@converter_bp.route('/convert/preview', methods=['POST'])
def convert_preview():
    parsed = _parse_conversion_request(request)
    if 'error' in parsed:
        return jsonify({'error': parsed['error'][0]}), parsed['error'][1]

    try:
        df, _, _ = transform_excel_with_mapping(
            parsed['input_path'],
            parsed['mapping'],
            parsed['dept_config'],
            parsed['articles_config'],
            parsed['start_date'],
            parsed['period_overrides'],
            parsed['ignore_depts'],
        )
        for col in ['Лимит', 'Баланс']:
            if col in df.columns:
                df[col] = df[col].round(2)

        preview_df = df.head(50)
        preview_data = preview_df.to_dict(orient='records')
        return jsonify({
            'columns': preview_df.columns.tolist(),
            'data': preview_data,
            'total_rows': len(df),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        safe_remove(parsed['input_path'])


@converter_bp.route('/convert/download', methods=['POST'])
def convert_download():
    parsed = _parse_conversion_request(request)
    if 'error' in parsed:
        return jsonify({'error': parsed['error'][0]}), parsed['error'][1]

    try:
        df, _, _ = transform_excel_with_mapping(
            parsed['input_path'],
            parsed['mapping'],
            parsed['dept_config'],
            parsed['articles_config'],
            parsed['start_date'],
            parsed['period_overrides'],
            parsed['ignore_depts'],
        )
        file_id = uuid.uuid4().hex
        output_path = os.path.join(parsed['upload_dir'], f'temp_result_{file_id}.xlsx')
        df.to_excel(output_path, index=False, float_format='%.2f')
        return jsonify({'file_id': file_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        safe_remove(parsed['input_path'])


@converter_bp.route('/convert/download_temp/<file_id>', methods=['GET'])
def download_temp_file(file_id):
    # Защита от path traversal: разрешены только hex-символы
    import re as re_mod
    if not re_mod.match(r'^[a-fA-F0-9]+$', file_id):
        return jsonify({'error': 'Некорректный идентификатор файла'}), 400

    upload_dir = _cfg('uploads')
    temp_path = os.path.join(upload_dir, f'temp_result_{file_id}.xlsx')
    if not os.path.exists(temp_path):
        return jsonify({'error': 'Файл не найден'}), 404

    # Проверка, что файл действительно внутри upload_dir (защита от path traversal)
    real_path = os.path.realpath(temp_path)
    real_upload = os.path.realpath(upload_dir)
    if not real_path.startswith(real_upload + os.sep):
        return jsonify({'error': 'Доступ запрещён'}), 403

    try:
        return send_file(
            temp_path,
            as_attachment=True,
            download_name='выгрузка.xlsx',
        )
    finally:
        # Удаляем temp-файл после отправки (чтобы не накапливались в uploads/)
        safe_remove(temp_path)
