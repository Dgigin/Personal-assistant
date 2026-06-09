# -*- coding: utf-8 -*-
"""
Юнит-тесты для функций модуля src/services/constructor.py.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.constructor import (
    _parse_dates_flexible,
    _infer_column_types,
    _infer_column_types_from_df,
    decompose_date_column,
    _apply_filters_to_df,
    _detect_header_row,
    build_pivot_table,
    _humanize_pivot_columns,
    build_pivot_async,
    get_pivot_task_status,
    cleanup_old_pivot_tasks,
    AGG_COLUMN_NAME,
    DATE_PREFIXES,
    DATE_PREFIX_DISPLAY,
)

from src.utils.file_utils import read_file_to_df


# ==================== _parse_dates_flexible ====================

class TestParseDatesFlexible:
    """Тесты для _parse_dates_flexible."""

    def test_iso_format(self):
        """ISO-формат: 2026-05-01, 2026-05-01 15:12:16."""
        series = pd.Series(['2026-05-01', '2026-06-15 15:12:16', 'abc'])
        result = _parse_dates_flexible(series)
        assert result.notna().sum() == 2
        assert result.iloc[0].month == 5
        assert result.iloc[0].day == 1

    def test_russian_format(self):
        """Русский формат: 01.05.2026, 31.12.2026."""
        series = pd.Series(['01.05.2026', '31.12.2026', 'не дата'])
        result = _parse_dates_flexible(series)
        assert result.notna().sum() == 2
        assert result.iloc[0].month == 5
        assert result.iloc[0].day == 1

    def test_nat_and_empty(self):
        """NaT и пустые строки."""
        series = pd.Series([pd.NaT, '', '2026-01-01'])
        result = _parse_dates_flexible(series)
        assert result.notna().sum() == 1

    def test_mixed_formats(self):
        """Смешанные форматы в одной серии."""
        series = pd.Series(['2026-03-10', '15.01.2026', 'не дата'])
        result = _parse_dates_flexible(series)
        assert result.notna().sum() == 2
        assert result.iloc[1].month == 1  # 15.01.2026 → январь
        assert result.iloc[1].day == 15


# ==================== _infer_column_types ====================

class TestInferColumnTypes:
    """Тесты для _infer_column_types."""

    def test_number_detection(self, tmp_excel):
        """Числовые колонки должны опознаваться как 'number'."""
        dtypes = _infer_column_types(tmp_excel, 'Sheet1', ['Продажи', 'Кол-во', 'Город'])
        assert dtypes.get('Продажи') == 'number'
        assert dtypes.get('Кол-во') == 'number'
        assert dtypes.get('Город') == 'text'

    def test_missing_column(self, tmp_excel):
        """Отсутствующая колонка → 'text'."""
        dtypes = _infer_column_types(tmp_excel, 'Sheet1', ['Несуществующая'])
        assert dtypes.get('Несуществующая') == 'text'


# ==================== _infer_column_types_from_df ====================

class TestInferColumnTypesFromDF:
    """Тесты для _infer_column_types_from_df."""

    def test_number_and_text(self):
        """Определение number и text по DataFrame."""
        df = pd.DataFrame({
            'Числа': ['100', '200', '300', 'abc'],
            'Текст': ['A', 'B', 'C', 'D'],
        })
        dtypes = _infer_column_types_from_df(df, ['Числа', 'Текст'])
        assert dtypes.get('Числа') == 'number'
        assert dtypes.get('Текст') == 'text'

    def test_empty_series(self):
        """Пустая колонка → 'text'."""
        df = pd.DataFrame({'Пусто': ['', '', '']})
        dtypes = _infer_column_types_from_df(df, ['Пусто'])
        assert dtypes.get('Пусто') == 'text'


# ==================== decompose_date_column ====================

class TestDecomposeDateColumn:
    """Тесты для decompose_date_column."""

    def test_decompose_valid(self):
        """Разбивка валидных дат."""
        series = pd.Series(['2026-01-15', '2026-03-10', '2026-12-25'])
        result = decompose_date_column(series, 'Дата')
        assert f'__год__Дата' in result
        assert f'__месяц__Дата' in result
        assert result[f'__год__Дата'].iloc[0] == '2026'
        assert result[f'__месяц__Дата'].iloc[0] == 'Январь'
        assert result[f'__день__Дата'].iloc[0] == '15'
        assert result[f'__квартал__Дата'].iloc[0] == 'Q1'

    def test_decompose_with_nat(self):
        """NaT-даты должны давать пустую строку."""
        series = pd.Series(['2026-01-15', pd.NaT, '2026-03-10'])
        # Преобразуем NaT-объекты в строку 'NaT' для сериализации
        series_str = series.astype(str)
        result = decompose_date_column(series_str, 'Дата')
        assert result[f'__год__Дата'].iloc[1] == ''

    def test_all_four_components(self):
        """Проверка всех 4 компонентов."""
        series = pd.Series(['2026-04-05'])
        result = decompose_date_column(series, 'Дата')
        assert f'__год__Дата' in result
        assert f'__квартал__Дата' in result
        assert f'__месяц__Дата' in result
        assert f'__день__Дата' in result
        prefix_count = sum(1 for key in result if any(key.startswith(p) for p in DATE_PREFIXES))
        assert prefix_count == 4


# ==================== _apply_filters_to_df ====================

class TestApplyFiltersToDF:
    """Тесты для _apply_filters_to_df."""

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            'Город': ['Москва', 'СПб', 'Казань', 'Москва'],
            'Продажи': ['100', '200', '150', '120'],
            'Статус': ['Активно', 'Активно', 'Закрыто', ''],
        })

    def test_equals(self, sample_df):
        result = _apply_filters_to_df(sample_df, {'Город': {'type': 'equals', 'value': 'Москва'}})
        assert len(result) == 2
        assert all(result['Город'] == 'Москва')

    def test_contains(self, sample_df):
        result = _apply_filters_to_df(sample_df, {'Город': {'type': 'contains', 'value': 'Мос'}})
        assert len(result) == 2

    def test_not_equals(self, sample_df):
        result = _apply_filters_to_df(sample_df, {'Город': {'type': 'not_equals', 'value': 'Москва'}})
        assert len(result) == 2

    def test_greater_than(self, sample_df):
        result = _apply_filters_to_df(sample_df, {'Продажи': {'type': 'greater_than', 'value': '120'}})
        assert len(result) == 2

    def test_less_than(self, sample_df):
        result = _apply_filters_to_df(sample_df, {'Продажи': {'type': 'less_than', 'value': '150'}})
        assert len(result) == 2
        assert all(int(v) < 150 for v in result['Продажи'])

    def test_is_empty(self, sample_df):
        result = _apply_filters_to_df(sample_df, {'Статус': {'type': 'is_empty', 'value': ''}})
        assert len(result) == 1

    def test_is_not_empty(self, sample_df):
        result = _apply_filters_to_df(sample_df, {'Статус': {'type': 'is_not_empty', 'value': ''}})
        assert len(result) == 3

    def test_no_filters(self, sample_df):
        result = _apply_filters_to_df(sample_df, None)
        assert len(result) == 4

    def test_empty_filters(self, sample_df):
        result = _apply_filters_to_df(sample_df, {})
        assert len(result) == 4


# ==================== _detect_header_row ====================

class TestDetectHeaderRow:
    """Тесты для _detect_header_row."""

    def test_normal_excel(self, tmp_excel):
        """Обычный Excel с заголовками в первой строке."""
        result = _detect_header_row(tmp_excel, 'Sheet1')
        assert result['best_header_row'] == 0
        assert 'rows_preview' in result
        assert len(result['rows_preview']) > 0

    def test_normal_csv(self, tmp_csv):
        """CSV с заголовками в первой строке."""
        # Для CSV читаем как виртуальный лист
        result = _detect_header_row(tmp_csv, os.path.splitext(os.path.basename(tmp_csv))[0])
        assert 'best_header_row' in result
        assert 'rows_preview' in result


# ==================== build_pivot_table ====================

class TestBuildPivotTable:
    """Тесты для build_pivot_table."""

    def test_basic_pivot_sum(self, tmp_excel):
        """Базовый pivot с одной агрегацией sum."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
        )
        assert 'pivot_data' in result
        assert 'columns' in result
        assert result['total_rows'] > 0
        # Должно быть 2 города: Москва, СПб
        assert result['total_rows'] == 2
        # Проверяем суммы
        data = {row['Город']: row for row in result['pivot_data']}
        assert 'Москва' in data
        assert 'СПб' in data
        assert float(data['Москва']['Продажи (Сумма)']) == 370  # 100+150+120
        assert float(data['СПб']['Продажи (Сумма)']) == 630  # 200+250+180

    def test_basic_pivot_count(self, tmp_excel):
        """Pivot с count."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['count'],
        )
        data = {row['Город']: row for row in result['pivot_data']}
        assert float(data['Москва']['Продажи (Количество)']) == 3
        assert float(data['СПб']['Продажи (Количество)']) == 3

    def test_multi_agg(self, tmp_excel):
        """Мульти-агрегация: sum + count."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum', 'count'],
        )
        data = {row['Город']: row for row in result['pivot_data']}
        assert 'Продажи (Сумма)' in result['columns']
        assert 'Продажи (Количество)' in result['columns']
        assert float(data['Москва']['Продажи (Сумма)']) == 370
        assert float(data['Москва']['Продажи (Количество)']) == 3

    def test_hierarchical_format(self, tmp_excel):
        """Иерархический формат вывода."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum', 'count'],
            output_format='hierarchical',
        )
        # В иерархическом формате должна быть колонка AGG_COLUMN_NAME
        assert AGG_COLUMN_NAME in result['columns']
        assert result['output_format'] == 'hierarchical'

    def test_none_agg(self, tmp_excel):
        """Агрегация 'none' (без изменений)."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['none'],
        )
        assert result['total_rows'] > 0
        assert 'message' in result
        # Проверяем, что все города сохранились
        cities = [row['Город'] for row in result['pivot_data']]
        assert 'Москва' in cities
        assert 'СПб' in cities

    def test_filters(self, tmp_excel):
        """Pivot с фильтром."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
            filters={'Город': {'type': 'equals', 'value': 'Москва'}},
        )
        assert result['total_rows'] == 1
        assert result['pivot_data'][0]['Город'] == 'Москва'

    def test_with_cols(self, tmp_excel):
        """Pivot с колонками (cols)."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=['Город'],
            values=['Продажи'],
            cols=['Месяц'],
            agg_functions=['sum'],
        )
        assert 'pivot_data' in result
        # В плоском формате могут быть колонки для каждого месяца
        янв_cols = [c for c in result['columns'] if 'Янв' in c]
        фев_cols = [c for c in result['columns'] if 'Фев' in c]
        assert len(янв_cols) > 0
        assert len(фев_cols) > 0

    def test_no_rows_or_values(self, tmp_excel):
        """Ошибка при отсутствии rows или values."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=[],
            values=[],
        )
        assert 'error' in result

    def test_totals_mode(self, tmp_excel):
        """Режим итогов 'both'."""
        result = build_pivot_table(
            tmp_excel, 'Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
            totals_mode='both',
        )
        data = {row['Город']: row for row in result['pivot_data']}
        assert 'Итого' in data

    def test_dates_decomposition(self, tmp_excel_dates):
        """Декомпозиция дат."""
        result = build_pivot_table(
            tmp_excel_dates, 'Sheet1',
            rows=['__год__Дата', '__месяц__Дата'],
            values=['Сумма'],
            agg_functions=['sum'],
        )
        # После _humanize_pivot_columns префиксы заменяются
        result_h = _humanize_pivot_columns(result)
        assert 'Год' in result_h['columns']
        assert 'Месяц' in result_h['columns']


# ==================== _humanize_pivot_columns ====================

class TestHumanizePivotColumns:
    """Тесты для _humanize_pivot_columns."""

    def test_date_prefixes_replaced(self):
        """Префиксы дат заменяются на читаемые названия."""
        result = {
            'columns': ['__год__Дата', '__месяц__Дата', 'Город', 'Сумма'],
            'pivot_data': [
                {'__год__Дата': '2026', '__месяц__Дата': 'Январь', 'Город': 'A', 'Сумма': '100'},
            ],
            'row_columns': ['__год__Дата', '__месяц__Дата'],
        }
        result = _humanize_pivot_columns(result)
        assert 'Год' in result['columns']
        assert 'Месяц' in result['columns']
        assert '__год__Дата' not in result['columns']
        assert '__месяц__Дата' not in result['columns']
        assert 'row_columns' in result
        assert result['row_columns'] == ['Год', 'Месяц']

    def test_no_dates(self):
        """Если нет колонок с префиксами, ничего не меняется."""
        result = {
            'columns': ['Город', 'Сумма', 'Продажи (Сумма)'],
            'pivot_data': [{'Город': 'Москва', 'Сумма': '100'}],
        }
        original = result.copy()
        result = _humanize_pivot_columns(result)
        assert result['columns'] == original['columns']


# ==================== АСИНХРОННЫЙ PIVOT ====================

class TestAsyncPivot:
    """Тесты для build_pivot_async, get_pivot_task_status, cleanup_old_pivot_tasks."""

    def test_build_pivot_async_queued(self, tmp_excel):
        """Запуск асинхронного pivot — задача в очереди."""
        task_id = build_pivot_async(
            file_path=tmp_excel,
            sheet_name='Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
        )
        assert task_id is not None
        assert isinstance(task_id, str)
        assert len(task_id) == 32  # UUID hex

    def test_pivot_task_status_queued(self, tmp_excel):
        """Статус задачи — 'queued' сразу после запуска."""
        task_id = build_pivot_async(
            file_path=tmp_excel,
            sheet_name='Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
        )
        status = get_pivot_task_status(task_id)
        assert status is not None
        assert status['status'] in ('queued', 'running', 'completed')
        assert status['progress'] >= 0.0

    def test_pivot_task_completion(self, tmp_excel):
        """Асинхронный pivot должен завершиться с результатом."""
        task_id = build_pivot_async(
            file_path=tmp_excel,
            sheet_name='Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
        )
        # Ждём завершения (максимум 10 секунд)
        import time
        deadline = time.time() + 10
        result = None
        while time.time() < deadline:
            status = get_pivot_task_status(task_id)
            if status['status'] == 'completed':
                result = status['result']
                break
            elif status['status'] == 'error':
                pytest.fail(f"Асинхронный pivot упал: {status.get('error')}")
            time.sleep(0.3)
        assert result is not None
        assert 'pivot_data' in result
        assert 'columns' in result

    def test_pivot_task_error_invalid_file(self):
        """Запуск с несуществующим файлом → статус 'error'."""
        task_id = build_pivot_async(
            file_path='/nonexistent/file.xlsx',
            sheet_name='Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
        )
        import time
        deadline = time.time() + 10
        error_status = None
        while time.time() < deadline:
            status = get_pivot_task_status(task_id)
            if status['status'] in ('completed', 'error'):
                error_status = status
                break
            time.sleep(0.3)
        assert error_status is not None
        assert error_status['status'] == 'error'

    def test_get_pivot_task_status_not_found(self):
        """Запрос статуса несуществующей задачи → None."""
        status = get_pivot_task_status('nonexistent_task_id_12345')
        assert status is None

    def test_cleanup_old_pivot_tasks(self, tmp_excel):
        """Очистка старых задач."""
        # Создаём задачу и ждём её завершения
        task_id = build_pivot_async(
            file_path=tmp_excel,
            sheet_name='Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
        )
        import time
        deadline = time.time() + 10
        while time.time() < deadline:
            status = get_pivot_task_status(task_id)
            if status and status['status'] in ('completed', 'error'):
                break
            time.sleep(0.3)

        # Подменяем created_at в прошлом
        from src.services.constructor import _pivot_tasks, _pivot_tasks_lock
        with _pivot_tasks_lock:
            if task_id in _pivot_tasks:
                _pivot_tasks[task_id]['created_at'] = time.time() - 7200  # 2 часа назад

        # Очищаем с max_age=1 час
        removed = cleanup_old_pivot_tasks(max_age_seconds=3600)
        assert removed >= 1
        assert get_pivot_task_status(task_id) is None

    def test_build_pivot_async_with_filters(self, tmp_excel):
        """Асинхронный pivot с фильтрами."""
        task_id = build_pivot_async(
            file_path=tmp_excel,
            sheet_name='Sheet1',
            rows=['Город'],
            values=['Продажи'],
            agg_functions=['sum'],
            filters={'Город': {'type': 'equals', 'value': 'Москва'}},
        )
        import time
        deadline = time.time() + 10
        result = None
        while time.time() < deadline:
            status = get_pivot_task_status(task_id)
            if status['status'] == 'completed':
                result = status['result']
                break
            elif status['status'] == 'error':
                pytest.fail(f"Асинхронный pivot с фильтром упал: {status.get('error')}")
            time.sleep(0.3)
        assert result is not None
        # Должна быть только Москва (2 строки: Янв 100 + Фев 150 + Мар 120 = 370)
        pivot_data = result.get('pivot_data', [])
        assert len(pivot_data) > 0
        москва_строки = [r for r in pivot_data if r.get('Город') == 'Москва']
        assert len(москва_строки) > 0
