# -*- coding: utf-8 -*-
"""
TypedDict-схемы для типизации структур данных приложения.
"""

from typing import TypedDict, List, Dict, Any, Optional


class FilterDef(TypedDict, total=False):
    """Определение фильтра для колонки."""
    type: str          # equals, contains, not_equals, greater_than, less_than, is_empty, is_not_empty
    value: str


class PivotResult(TypedDict, total=False):
    """Результат построения сводной таблицы."""
    pivot_data: List[Dict[str, Any]]
    columns: List[str]
    total_rows: int
    aggregations: List[str]
    output_format: str
    error: str
    row_columns: Optional[List[str]]
    agg_column: Optional[str]
    message: Optional[str]


class ScenarioParams(TypedDict, total=False):
    """Параметры сценария конструктора."""
    columns: List[str]
    filters: Dict[str, FilterDef]
    pivot_rows: List[str]
    pivot_values: List[str]
    pivot_cols: List[str]
    agg_functions: List[str]
    output_format: str


class ScenarioData(TypedDict, total=False):
    """Сценарий конструктора (JSON-файл)."""
    name: str
    created_at: str
    updated_at: str
    params: ScenarioParams


class LoadSheetResult(TypedDict, total=False):
    """Результат загрузки листа Excel."""
    columns: List[str]
    total_rows: int
    file_path: str
    sheet_name: str
    dtypes: Dict[str, str]


class ApplyFiltersResult(TypedDict, total=False):
    """Результат применения фильтров."""
    columns: List[str]
    data: List[Dict[str, Any]]
    total_rows: int
    filtered_count: int
