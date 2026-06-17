# -*- coding: utf-8 -*-
"""
Сервис конструктора отчётов (Report Builder).

Позволяет создавать, сохранять, загружать и экспортировать отчёты,
состоящие из блоков: текст, сводная таблица, график, статистика, данные.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, TypedDict, Literal
from io import BytesIO

import pandas as pd

logger = logging.getLogger(__name__)

# =====================================================================
# ТИПЫ ДАННЫХ
# =====================================================================


class BlockBase(TypedDict, total=False):
    """Базовый блок отчёта."""
    id: str
    type: str  # 'text', 'pivot', 'chart', 'stats', 'data'
    title: str


class TextBlock(BlockBase):
    """Текстовый блок."""
    type: Literal['text']
    content: str          # Markdown-текст
    font_size: str        # 'small', 'normal', 'large', 'h1', 'h2', 'h3'
    align: str            # 'left', 'center', 'right'


class PivotBlock(BlockBase):
    """Блок сводной таблицы (ссылка на сценарий конструктора)."""
    type: Literal['pivot']
    scenario_name: str    # Имя сохранённого сценария конструктора
    scenario_params: Optional[Dict[str, Any]]  # Замороженные параметры


class ChartBlock(BlockBase):
    """Блок графика."""
    type: Literal['chart']
    chart_type: str       # 'bar', 'line', 'pie', 'doughnut'
    chart_data: Dict[str, Any]  # Данные для Chart.js
    chart_options: Dict[str, Any]  # Опции Chart.js
    width: int            # 1-12 колонок (сетка)
    height: int           # Высота в пикселях


class StatsBlock(BlockBase):
    """Блок статистики (ключевые метрики)."""
    type: Literal['stats']
    metrics: List[Dict[str, Any]]  # [{label, value, color, icon}]


class DataBlock(BlockBase):
    """Блок исходных данных."""
    type: Literal['data']
    columns: List[str]
    data: List[Dict[str, Any]]
    max_rows: int         # Лимит отображаемых строк
    source: str           # 'constructor', 'upload', 'reference'

# =====================================================================
# МОДЕЛЬ ОТЧЁТА
# =====================================================================


ReportBlock = Dict[str, Any]  # Any of BlockBase subtypes

# Директория для хранения отчётов
REPORTS_DIR: str = ''
REPORT_TEMPLATES_DIR: str = ''


def init_report_dirs(config_dir: str) -> None:
    """Инициализация директорий для хранения отчётов."""
    global REPORTS_DIR, REPORT_TEMPLATES_DIR
    REPORTS_DIR = os.path.join(config_dir, 'reports')
    REPORT_TEMPLATES_DIR = os.path.join(config_dir, 'report_templates')
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(REPORT_TEMPLATES_DIR, exist_ok=True)


def _get_report_path(name: str) -> str:
    """Получить путь к файлу отчёта."""
    safe_name = name.replace('/', '_').replace('\\', '_').strip()
    return os.path.join(REPORTS_DIR, f'{safe_name}.json')


def _get_template_path(name: str) -> str:
    """Получить путь к файлу шаблона."""
    safe_name = name.replace('/', '_').replace('\\', '_').strip()
    return os.path.join(REPORT_TEMPLATES_DIR, f'{safe_name}.json')


def create_report(name: str) -> Dict[str, Any]:
    """Создать новый пустой отчёт."""
    report = {
        'name': name,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'blocks': [],
        'page_size': 'A4',
        'orientation': 'portrait',  # 'portrait' | 'landscape'
    }
    return report


def save_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Сохранить отчёт в JSON."""
    name = report.get('name', 'untitled')
    if not name:
        return {'error': 'Имя отчёта не указано'}

    report['updated_at'] = datetime.now().isoformat()
    path = _get_report_path(name)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info('Отчёт "%s" сохранён', name)
        return {'success': True, 'name': name}
    except Exception as e:
        logger.error('Ошибка сохранения отчёта "%s": %s', name, e)
        return {'error': f'Ошибка сохранения: {e}'}


def load_report(name: str) -> Dict[str, Any]:
    """Загрузить отчёт по имени."""
    path = _get_report_path(name)
    if not os.path.exists(path):
        return {'error': f'Отчёт "{name}" не найден'}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error('Ошибка загрузки отчёта "%s": %s', name, e)
        return {'error': f'Ошибка загрузки: {e}'}


def delete_report(name: str) -> Dict[str, Any]:
    """Удалить отчёт."""
    path = _get_report_path(name)
    if not os.path.exists(path):
        return {'error': f'Отчёт "{name}" не найден'}
    try:
        os.remove(path)
        logger.info('Отчёт "%s" удалён', name)
        return {'success': True, 'name': name}
    except Exception as e:
        logger.error('Ошибка удаления отчёта "%s": %s', name, e)
        return {'error': f'Ошибка удаления: {e}'}


def list_reports() -> List[Dict[str, Any]]:
    """Список всех сохранённых отчётов."""
    reports = []
    if not os.path.exists(REPORTS_DIR):
        return reports
    for fname in sorted(os.listdir(REPORTS_DIR)):
        if fname.endswith('.json'):
            fpath = os.path.join(REPORTS_DIR, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    reports.append({
                        'name': data.get('name', fname[:-5]),
                        'created_at': data.get('created_at', ''),
                        'updated_at': data.get('updated_at', ''),
                        'block_count': len(data.get('blocks', [])),
                    })
            except Exception:
                reports.append({
                    'name': fname[:-5],
                    'created_at': '',
                    'updated_at': '',
                    'block_count': 0,
                })
    return reports


# =====================================================================
# РАБОТА С БЛОКАМИ
# =====================================================================


def add_block(report: Dict[str, Any], block: Dict[str, Any],
              index: Optional[int] = None) -> Dict[str, Any]:
    """Добавить блок в отчёт (на указанную позицию или в конец)."""
    if 'blocks' not in report:
        report['blocks'] = []

    if 'id' not in block:
        block['id'] = str(uuid.uuid4())[:8]

    if index is not None:
        report['blocks'].insert(index, block)
    else:
        report['blocks'].append(block)

    report['updated_at'] = datetime.now().isoformat()
    return report


def update_block(report: Dict[str, Any], block_id: str,
                 updates: Dict[str, Any]) -> Dict[str, Any]:
    """Обновить блок отчёта по ID."""
    for i, block in enumerate(report.get('blocks', [])):
        if block.get('id') == block_id:
            updated = {**block, **updates}
            updated['id'] = block_id  # ID не меняем
            report['blocks'][i] = updated
            report['updated_at'] = datetime.now().isoformat()
            return report
    return report


def remove_block(report: Dict[str, Any], block_id: str) -> Dict[str, Any]:
    """Удалить блок из отчёта по ID."""
    report['blocks'] = [b for b in report.get('blocks', [])
                        if b.get('id') != block_id]
    report['updated_at'] = datetime.now().isoformat()
    return report


def reorder_blocks(report: Dict[str, Any], block_ids: List[str]) -> Dict[str, Any]:
    """Переставить блоки отчёта в указанном порядке."""
    block_map = {b.get('id'): b for b in report.get('blocks', [])}
    new_blocks = []
    for bid in block_ids:
        if bid in block_map:
            new_blocks.append(block_map[bid])
    report['blocks'] = new_blocks
    report['updated_at'] = datetime.now().isoformat()
    return report


# =====================================================================
# ЭКСПОРТ
# =====================================================================


def export_to_xlsx(report: Dict[str, Any]) -> Optional[BytesIO]:
    """Экспорт отчёта в многостраничный XLSX."""
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Лист с информацией об отчёте
            info_df = pd.DataFrame({
                'Параметр': ['Название отчёта', 'Создан', 'Изменён'],
                'Значение': [
                    report.get('name', ''),
                    report.get('created_at', ''),
                    report.get('updated_at', ''),
                ]
            })
            info_df.to_excel(writer, sheet_name='О_отчёте', index=False)

            # Каждый блок — отдельный лист
            for i, block in enumerate(report.get('blocks', [])):
                block_type = block.get('type', 'unknown')
                block_title = block.get('title', f'Блок {i + 1}')
                sheet_name = f'{block_title[:25]}'  # Ограничение длины имени листа

                if block_type == 'stats':
                    # Статистика — простая таблица метрик
                    metrics = block.get('metrics', [])
                    if metrics:
                        df = pd.DataFrame(metrics)
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    else:
                        pd.DataFrame({'': ['Нет данных']}).to_excel(
                            writer, sheet_name=sheet_name, index=False)

                elif block_type == 'data':
                    # Таблица данных
                    data = block.get('data', [])
                    columns = block.get('columns', [])
                    if data and columns:
                        df = pd.DataFrame(data, columns=columns)
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    else:
                        pd.DataFrame({'': ['Нет данных']}).to_excel(
                            writer, sheet_name=sheet_name, index=False)

                elif block_type == 'text':
                    # Текст — одна колонка с содержанием
                    content = block.get('content', '')
                    pd.DataFrame({'Текст': [content]}).to_excel(
                        writer, sheet_name=sheet_name, index=False)

                elif block_type == 'pivot':
                    # Сводная — будет заполнена при экспорте из реальных данных
                    pd.DataFrame({'': ['Данные сводной таблицы']}).to_excel(
                        writer, sheet_name=sheet_name, index=False)

                elif block_type == 'chart':
                    # График — данные графика
                    chart_data = block.get('chart_data', {})
                    labels = chart_data.get('labels', [])
                    datasets = chart_data.get('datasets', [])
                    if datasets:
                        chart_df = pd.DataFrame({
                            ds.get('label', f'Ряд {i}') if isinstance(ds, dict) else 'Данные': ds.get('data', []) if isinstance(ds, dict) else []
                            for i, ds in enumerate(datasets)
                        })
                        if labels:
                            chart_df.insert(0, 'Метки', labels)
                        chart_df.to_excel(writer, sheet_name=f'График_{block_title[:15]}', index=False)
                    else:
                        pd.DataFrame({'': ['Нет данных графика']}).to_excel(
                            writer, sheet_name=sheet_name, index=False)

        output.seek(0)
        return output
    except Exception as e:
        logger.error('Ошибка экспорта отчёта в XLSX: %s', e)
        return None


# =====================================================================
# ТЕМПЛЕЙТЫ (готовые шаблоны отчётов)
# =====================================================================


def get_default_templates() -> Dict[str, Dict[str, Any]]:
    """Возвращает словарь готовых шаблонов отчётов."""
    return {
        'sales_report': {
            'name': 'Продажи',
            'template_name': 'sales_report',
            'description': 'Отчёт по продажам: сводная + график + статистика',
            'blocks': [
                {
                    'id': 'text_01',
                    'type': 'text',
                    'title': 'Заголовок',
                    'content': '# 📊 Отчёт по продажам\n\nАвтоматический отчёт по данным продаж.',
                    'font_size': 'h1',
                    'align': 'center',
                },
                {
                    'id': 'stats_01',
                    'type': 'stats',
                    'title': 'Ключевые показатели',
                    'metrics': [
                        {'label': 'Всего продаж', 'value': '—', 'color': '#28a745', 'icon': '💰'},
                        {'label': 'Средний чек', 'value': '—', 'color': '#007bff', 'icon': '📊'},
                        {'label': 'Кол-во транзакций', 'value': '—', 'color': '#17a2b8', 'icon': '📋'},
                        {'label': 'Лучший месяц', 'value': '—', 'color': '#ffc107', 'icon': '🏆'},
                    ],
                },
                {
                    'id': 'chart_01',
                    'type': 'chart',
                    'title': 'Динамика продаж',
                    'chart_type': 'bar',
                    'width': 12,
                    'height': 300,
                    'chart_data': {'labels': [], 'datasets': []},
                    'chart_options': {},
                },
                {
                    'id': 'pivot_01',
                    'type': 'pivot',
                    'title': 'Сводная по менеджерам',
                    'scenario_name': '',
                    'scenario_params': None,
                },
            ],
        },
        'finance_report': {
            'name': 'Финансы',
            'template_name': 'finance_report',
            'description': 'Финансовый отчёт: доходы/расходы, структура затрат',
            'blocks': [
                {
                    'id': 'text_01',
                    'type': 'text',
                    'title': 'Заголовок',
                    'content': '# 💰 Финансовый отчёт',
                    'font_size': 'h1',
                    'align': 'center',
                },
                {
                    'id': 'chart_01',
                    'type': 'chart',
                    'title': 'Структура затрат',
                    'chart_type': 'pie',
                    'width': 6,
                    'height': 300,
                    'chart_data': {'labels': [], 'datasets': []},
                    'chart_options': {},
                },
                {
                    'id': 'chart_02',
                    'type': 'chart',
                    'title': 'Динамика доходов/расходов',
                    'chart_type': 'line',
                    'width': 6,
                    'height': 300,
                    'chart_data': {'labels': [], 'datasets': []},
                    'chart_options': {},
                },
            ],
        },
        'hr_report': {
            'name': 'HR',
            'template_name': 'hr_report',
            'description': 'HR-отчёт: сотрудники по отделам, динамика, средняя ЗП',
            'blocks': [
                {
                    'id': 'text_01',
                    'type': 'text',
                    'title': 'Заголовок',
                    'content': '# 👥 HR-отчёт',
                    'font_size': 'h1',
                    'align': 'center',
                },
                {
                    'id': 'stats_01',
                    'type': 'stats',
                    'title': 'Ключевые показатели',
                    'metrics': [
                        {'label': 'Всего сотрудников', 'value': '—', 'color': '#28a745', 'icon': '👥'},
                        {'label': 'Средняя ЗП', 'value': '—', 'color': '#007bff', 'icon': '💰'},
                        {'label': 'Отделов', 'value': '—', 'color': '#17a2b8', 'icon': '🏢'},
                    ],
                },
                {
                    'id': 'chart_01',
                    'type': 'chart',
                    'title': 'Сотрудники по отделам',
                    'chart_type': 'bar',
                    'width': 12,
                    'height': 300,
                    'chart_data': {'labels': [], 'datasets': []},
                    'chart_options': {},
                },
            ],
        },
    }


# =====================================================================
# ПРЕДПРОСМОТР (генерация HTML)
# =====================================================================


def preview_report_html(report: Dict[str, Any],
                        chart_data_map: Optional[Dict[str, str]] = None) -> str:
    """Генерирует HTML-предпросмотр отчёта."""
    name = report.get('name', 'Отчёт')
    blocks = report.get('blocks', [])

    parts = [f'<div class="report-preview" style="padding:20px;max-width:1200px;margin:0 auto;font-family:Arial,sans-serif;">']
    parts.append(f'<h1 style="text-align:center;color:#333;margin-bottom:24px;">📄 {name}</h1>')

    for block in blocks:
        block_type = block.get('type', 'unknown')
        block_title = block.get('title', '')

        if block_type == 'text':
            font_size = block.get('font_size', 'normal')
            align = block.get('align', 'left')
            sizes = {'small': '12px', 'normal': '14px', 'large': '18px',
                     'h1': '28px', 'h2': '24px', 'h3': '20px'}
            fs = sizes.get(font_size, '14px')
            parts.append(
                f'<div style="text-align:{align};font-size:{fs};'
                f'margin-bottom:16px;padding:8px;border-radius:6px;'
                f'background:#f9f9f9;">{block.get("content", "")}</div>'
            )

        elif block_type == 'stats':
            metrics = block.get('metrics', [])
            if metrics:
                cards = ''
                for m in metrics:
                    icon = m.get('icon', '📊')
                    label = m.get('label', '')
                    value = m.get('value', '—')
                    color = m.get('color', '#007bff')
                    cards += (
                        f'<div style="flex:1;min-width:150px;padding:16px;'
                        f'border-radius:8px;background:#fff;border:1px solid #ddd;'
                        f'text-align:center;margin:4px;">'
                        f'<div style="font-size:28px;">{icon}</div>'
                        f'<div style="font-size:12px;color:#666;margin:4px 0;">{label}</div>'
                        f'<div style="font-size:22px;font-weight:700;color:{color};">{value}</div>'
                        f'</div>'
                    )
                parts.append(
                    f'<div style="margin-bottom:16px;">'
                    f'{"<h3 style=\"margin:0 0 8px 4px;\">📊 " + block_title + "</h3>" if block_title else ""}'
                    f'<div style="display:flex;flex-wrap:wrap;gap:4px;">{cards}</div>'
                    f'</div>'
                )

        elif block_type == 'data':
            columns = block.get('columns', [])
            data = block.get('data', [])
            if columns and data:
                table = '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
                table += '<thead><tr>'
                for col in columns:
                    table += f'<th style="border:1px solid #ddd;padding:6px;background:#f1f1f1;font-weight:600;">{col}</th>'
                table += '</tr></thead><tbody>'
                for row in data[:50]:  # Лимит 50 строк в предпросмотре
                    table += '<tr>'
                    for col in columns:
                        val = row.get(col, '')
                        table += f'<td style="border:1px solid #ddd;padding:4px;">{val}</td>'
                    table += '</tr>'
                table += '</tbody></table>'
                parts.append(
                    f'<div style="margin-bottom:16px;overflow-x:auto;">'
                    f'{"<h3 style=\"margin:0 0 8px 4px;\">📋 " + block_title + "</h3>" if block_title else ""}'
                    f'{table}'
                    f'</div>'
                )

        elif block_type == 'pivot':
            parts.append(
                f'<div style="margin-bottom:16px;padding:16px;background:#f0f8ff;'
                f'border:1px dashed #007bff;border-radius:8px;text-align:center;'
                f'color:#666;font-size:14px;">'
                f'📊 <strong>{block_title or "Сводная таблица"}</strong><br>'
                f'<span style="font-size:12px;">Данные будут загружены при формировании отчёта</span>'
                f'</div>'
            )

        elif block_type == 'chart':
            chart_id = f'report-chart-{block.get("id", "unknown")}'
            width = block.get('width', 12)
            chart_type = block.get('chart_type', 'bar')
            type_icon = {'bar': '📊', 'line': '📈', 'pie': '🥧', 'doughnut': '🍩'}
            icon = type_icon.get(chart_type, '📊')
            parts.append(
                f'<div class="chart-container" style="margin-bottom:16px;'
                f'width:{width/12*100}%;">'
                f'{"<h3 style=\"margin:0 0 8px 4px;\">" + icon + " " + block_title + "</h3>" if block_title else ""}'
                f'<canvas id="{chart_id}" style="border:1px solid #eee;border-radius:8px;'
                f'background:#fff;padding:8px;"></canvas>'
                f'</div>'
            )

    parts.append('</div>')
    return '\n'.join(parts)
