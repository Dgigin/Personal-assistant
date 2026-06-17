# -*- coding: utf-8 -*-
"""
API эндпоинты конструктора отчётов (Report Builder).
"""

import logging
from flask import Blueprint, request, jsonify

from src.services.report_builder import (
    init_report_dirs,
    create_report,
    save_report,
    load_report,
    delete_report,
    list_reports,
    add_block,
    update_block,
    remove_block,
    reorder_blocks,
    export_to_xlsx,
    get_default_templates,
    preview_report_html,
    REPORTS_DIR,
    REPORT_TEMPLATES_DIR,
)
from src.config import Config

logger = logging.getLogger(__name__)

report_bp = Blueprint('report', __name__, url_prefix='/api/report')


# -----------------------------------------------------------------------
# Инициализация директорий при первом импорте
# -----------------------------------------------------------------------
init_report_dirs(Config.CONFIG_DIR)


# -----------------------------------------------------------------------
# CRUD отчётов
# -----------------------------------------------------------------------

@report_bp.route('/create', methods=['POST'])
def api_create_report():
    """Создать новый пустой отчёт."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Укажите имя отчёта'}), 400
    report = create_report(name)
    result = save_report(report)
    return jsonify(result)


@report_bp.route('/save', methods=['POST'])
def api_save_report():
    """Сохранить отчёт."""
    report = request.get_json() or {}
    if not report.get('name'):
        return jsonify({'error': 'Имя отчёта не указано'}), 400
    result = save_report(report)
    return jsonify(result)


@report_bp.route('/load', methods=['POST'])
def api_load_report():
    """Загрузить отчёт по имени."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Укажите имя отчёта'}), 400
    report = load_report(name)
    if 'error' in report:
        return jsonify(report), 404
    return jsonify(report)


@report_bp.route('/delete', methods=['POST'])
def api_delete_report():
    """Удалить отчёт."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Укажите имя отчёта'}), 400
    result = delete_report(name)
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result)


@report_bp.route('/list', methods=['GET'])
def api_list_reports():
    """Список сохранённых отчётов."""
    reports = list_reports()
    return jsonify({'reports': reports})


# -----------------------------------------------------------------------
# Работа с блоками отчёта
# -----------------------------------------------------------------------

@report_bp.route('/block/add', methods=['POST'])
def api_add_block():
    """Добавить блок в отчёт."""
    data = request.get_json() or {}
    report = data.get('report', {})
    block = data.get('block', {})
    index = data.get('index')

    if not report.get('name'):
        return jsonify({'error': 'Отчёт не передан'}), 400
    if not block.get('type'):
        return jsonify({'error': 'Тип блока не указан'}), 400

    report = add_block(report, block, index)
    result = save_report(report)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify({'report': report, 'block_id': block.get('id', '')})


@report_bp.route('/block/update', methods=['POST'])
def api_update_block():
    """Обновить блок отчёта."""
    data = request.get_json() or {}
    report = data.get('report', {})
    block_id = data.get('block_id', '')
    updates = data.get('updates', {})

    if not report.get('name'):
        return jsonify({'error': 'Отчёт не передан'}), 400
    if not block_id:
        return jsonify({'error': 'ID блока не указан'}), 400

    report = update_block(report, block_id, updates)
    result = save_report(report)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify({'report': report})


@report_bp.route('/block/remove', methods=['POST'])
def api_remove_block():
    """Удалить блок из отчёта."""
    data = request.get_json() or {}
    report = data.get('report', {})
    block_id = data.get('block_id', '')

    if not report.get('name'):
        return jsonify({'error': 'Отчёт не передан'}), 400
    if not block_id:
        return jsonify({'error': 'ID блока не указан'}), 400

    report = remove_block(report, block_id)
    result = save_report(report)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify({'report': report})


@report_bp.route('/block/reorder', methods=['POST'])
def api_reorder_blocks():
    """Переставить блоки отчёта."""
    data = request.get_json() or {}
    report = data.get('report', {})
    block_ids = data.get('block_ids', [])

    if not report.get('name'):
        return jsonify({'error': 'Отчёт не передан'}), 400

    report = reorder_blocks(report, block_ids)
    result = save_report(report)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify({'report': report})


# -----------------------------------------------------------------------
# Предпросмотр и экспорт
# -----------------------------------------------------------------------

@report_bp.route('/preview', methods=['POST'])
def api_preview_report():
    """Сгенерировать HTML-предпросмотр отчёта."""
    report = request.get_json() or {}
    if not report.get('name'):
        return jsonify({'error': 'Отчёт не передан'}), 400
    html = preview_report_html(report)
    return jsonify({'html': html})


@report_bp.route('/export/xlsx', methods=['POST'])
def api_export_xlsx():
    """Экспорт отчёта в XLSX."""
    report = request.get_json() or {}
    if not report.get('name'):
        return jsonify({'error': 'Отчёт не передан'}), 400

    xlsx_data = export_to_xlsx(report)
    if xlsx_data is None:
        return jsonify({'error': 'Ошибка экспорта'}), 500

    # Сохраняем во временный файл и возвращаем ссылку
    import os
    import uuid
    from src.config import Config

    file_id = str(uuid.uuid4())
    temp_dir = os.path.join(Config.UPLOAD_DIR, 'report_exports')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f'{file_id}.xlsx')

    with open(temp_path, 'wb') as f:
        f.write(xlsx_data.getvalue())

    safe_name = report.get('name', 'отчёт').replace('/', '_').replace('\\', '_')
    return jsonify({
        'success': True,
        'file_id': file_id,
        'filename': f'{safe_name}.xlsx',
        'download_url': f'/convert/download_temp/{file_id}',
    })


# -----------------------------------------------------------------------
# Шаблоны
# -----------------------------------------------------------------------

@report_bp.route('/templates', methods=['GET'])
def api_get_templates():
    """Список готовых шаблонов отчётов."""
    templates = get_default_templates()
    result = []
    for key, tmpl in templates.items():
        result.append({
            'id': key,
            'name': tmpl.get('name', key),
            'description': tmpl.get('description', ''),
            'block_count': len(tmpl.get('blocks', [])),
        })
    return jsonify({'templates': result})


@report_bp.route('/template/load', methods=['POST'])
def api_load_template():
    """Загрузить шаблон отчёта."""
    data = request.get_json() or {}
    template_id = data.get('template_id', '').strip()
    if not template_id:
        return jsonify({'error': 'ID шаблона не указан'}), 400

    templates = get_default_templates()
    if template_id not in templates:
        return jsonify({'error': f'Шаблон "{template_id}" не найден'}), 404

    tmpl = templates[template_id]
    # Создаём отчёт из шаблона
    name = data.get('name', tmpl.get('name', template_id))
    report = create_report(name)
    report['blocks'] = tmpl.get('blocks', [])
    result = save_report(report)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(report)
