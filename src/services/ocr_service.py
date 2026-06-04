# -*- coding: utf-8 -*-
"""
Сервис OCR для распознавания текста и таблиц из изображений.
Использует EasyOCR как основной движок (с русской локалью).
"""

import os
import re
import json
import tempfile
from typing import List, Dict, Any, Optional, Tuple

from ..config import Config


# Lazy loading EasyOCR (первый запуск скачивает модели)
_reader = None


def get_reader():
    """Возвращает глобальный экземпляр EasyOCR Reader (ленивая инициализация)."""
    global _reader
    if _reader is None:
        import easyocr
        # Поддерживаемые языки: русский + английский (для распознавания таблиц)
        _reader = easyocr.Reader(
            ['ru', 'en'],
            gpu=False,  # CPU mode для совместимости
            verbose=False,
        )
    return _reader


def ocr_image(image_path: str) -> List[Dict[str, Any]]:
    """
    Распознаёт текст на изображении.
    
    :param image_path: Путь к файлу изображения
    :return: Список распознанных элементов:
        [{'text': str, 'confidence': float, 'bbox': [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]}, ...]
    """
    reader = get_reader()
    results = reader.readtext(image_path, paragraph=False)
    
    items = []
    for bbox, text, confidence in results:
        items.append({
            'text': text,
            'confidence': round(confidence, 3),
            'bbox': bbox,  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        })
    
    return items


def group_text_into_table(items: List[Dict[str, Any]], row_threshold: float = 0.3) -> List[List[Dict[str, Any]]]:
    """
    Группирует распознанные элементы в строки таблицы на основе Y-координат.
    
    :param items: Результат OCR (список элементов с bbox)
    :param row_threshold: Допуск по Y для группировки в одну строку (доля от высоты)
    :return: Список строк, где каждая строка — список элементов
    """
    if not items:
        return []
    
    # Сортируем по Y (средняя точка по вертикали)
    sorted_items = sorted(items, key=lambda x: (x['bbox'][0][1] + x['bbox'][2][1]) / 2)
    
    # Определяем высоту строки
    all_heights = [abs(item['bbox'][0][1] - item['bbox'][2][1]) for item in sorted_items]
    avg_height = sum(all_heights) / len(all_heights) if all_heights else 20
    
    threshold = avg_height * row_threshold
    
    rows = []
    current_row = []
    current_y = None
    
    for item in sorted_items:
        item_y = (item['bbox'][0][1] + item['bbox'][2][1]) / 2
        
        if current_y is None:
            current_y = item_y
            current_row.append(item)
        elif abs(item_y - current_y) <= threshold:
            # Тот же ряд
            current_row.append(item)
        else:
            # Новый ряд
            if current_row:
                # Сортируем элементы в ряду по X
                current_row.sort(key=lambda x: (x['bbox'][0][0] + x['bbox'][2][0]) / 2)
                rows.append(current_row)
            current_row = [item]
            current_y = item_y
    
    if current_row:
        current_row.sort(key=lambda x: (x['bbox'][0][0] + x['bbox'][2][0]) / 2)
        rows.append(current_row)
    
    return rows


def rows_to_text(rows: List[List[Dict[str, Any]]]) -> str:
    """Преобразует строки таблицы в текстовый формат (колонки разделены табуляцией)."""
    lines = []
    for row in rows:
        texts = [cell['text'] for cell in row]
        lines.append('\t'.join(texts))
    return '\n'.join(lines)


def rows_to_json(rows: List[List[Dict[str, Any]]]) -> Optional[List[Dict[str, str]]]:
    """
    Преобразует строки таблицы в JSON-массив объектов.
    Первая строка используется как заголовки колонок.
    """
    if not rows or len(rows) < 2:
        return None
    
    headers = [cell['text'].strip() for cell in rows[0]]
    if not headers:
        return None
    
    result = []
    for row in rows[1:]:
        values = [cell['text'].strip() for cell in row]
        obj = {}
        for i, header in enumerate(headers):
            value = values[i] if i < len(values) else ''
            obj[header] = value
        result.append(obj)
    
    return result


def extract_table_from_image(image_path: str) -> Dict[str, Any]:
    """
    Полный pipeline: OCR изображения -> группировка в таблицу -> JSON.
    
    :param image_path: Путь к изображению
    :return: Словарь с результатами:
        {
            'raw_text': str,          # Весь распознанный текст
            'table_text': str,        # Текст, сгруппированный в колонки/строки
            'table_json': list|None,  # JSON-массив с таблицей (если удалось распознать)
            'rows_count': int,        # Количество строк (включая заголовок)
            'items_count': int,       # Всего распознанных элементов
            'is_table': bool,         # Удалось ли распознать как таблицу
        }
    """
    items = ocr_image(image_path)
    
    if not items:
        return {
            'success': False,
            'raw_text': '',
            'table_text': '',
            'table_json': None,
            'rows_count': 0,
            'items_count': 0,
            'is_table': False,
        }
    
    # Весь текст подряд
    raw_text = ' '.join(item['text'] for item in items)
    
    # Группируем в таблицу
    rows = group_text_into_table(items)
    table_text = rows_to_text(rows)
    table_json = rows_to_json(rows)
    
    return {
        'success': True,
        'raw_text': raw_text,
        'table_text': table_text,
        'table_json': table_json,
        'rows_count': len(rows),
        'items_count': len(items),
        'is_table': table_json is not None and len(table_json) > 0,
    }
