# -*- coding: utf-8 -*-
"""
Сервис конвертации Excel: основная бизнес-логика трансформации.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

from ..utils.file_utils import read_file_to_df


def transform_excel_with_mapping(
    input_path: str,
    mapping: List[Dict[str, Any]],
    dept_config: Dict[str, str],
    articles_config: Dict[str, Dict[str, str]],
    start_date_str: str,
    period_overrides: Dict[str, int],
    ignore_depts: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Основная функция конвертации Excel-файла по заданным правилам.

    :param input_path: Путь к входному Excel-файлу
    :param mapping: Правила маппинга столбцов
    :param dept_config: Справочник подразделений {код: название}
    :param articles_config: Справочник статей расходов {код_столбца: {name, budget}}
    :param start_date_str: Дата начала в формате YYYY-MM-DD
    :param period_overrides: Переопределения периодов для столбцов {столбец: дни}
    :param ignore_depts: Список кодов подразделений для исключения
    :return: (DataFrame, список неизвестных подразделений, список неизвестных статей)
    """
    if ignore_depts is None:
        ignore_depts = []

    df_source = read_file_to_df(input_path, sheet_name=0, dtype=str)
    departments = df_source.iloc[:, 0].tolist()
    data_columns = df_source.columns[1:]

    # Парсинг даты
    try:
        date_obj = datetime.strptime(start_date_str, '%Y-%m-%d')
        date_short = date_obj.strftime('%d.%m.%Y')
    except Exception:
        date_short = start_date_str

    rows: List[Dict[str, Any]] = []
    unknown_depts: List[str] = []
    unknown_articles: List[str] = []

    for dept in departments:
        if pd.isna(dept):
            continue
        dept_code = str(dept).strip()
        if '/' in dept_code:
            dept_code = dept_code.split('/')[0].strip()

        if dept_code in ignore_depts:
            continue

        # Поиск названия подразделения
        if dept_code in dept_config:
            full_name = dept_config[dept_code]
        else:
            full_name = dept_code
            unknown_depts.append(dept_code)

        for rule in mapping:
            source_col = rule['source_column']
            if source_col not in data_columns:
                continue

            val = df_source.loc[df_source.iloc[:, 0] == dept, source_col].values
            limit = 0.0
            if len(val) > 0 and pd.notna(val[0]):
                try:
                    limit = float(val[0])
                except Exception:
                    limit = 0.0

            # Поиск статьи расходов
            if source_col in articles_config:
                art = articles_config[source_col]
                budget = art.get('budget', '')
                target_article = art.get('name', source_col)
            else:
                budget = rule.get('budget', '')
                target_article = rule.get('target_article', source_col)
                unknown_articles.append(source_col)

            period = period_overrides.get(source_col, rule.get('default_period', 30))

            rows.append({
                'Бюджет': budget,
                'Статья расходов': target_article,
                'Лимит': limit,
                'Баланс': limit,
                'Зарезервировано': 0,
                'Юр. лицо': '',
                'Подразделение': full_name,
                'Период': period,
                'Дата': date_short,
                'Активен': 'Да',
            })

    df = pd.DataFrame(rows)

    # Группировка и агрегация
    if not df.empty:
        group_cols = [
            'Бюджет', 'Статья расходов', 'Подразделение',
            'Период', 'Дата', 'Активен', 'Юр. лицо', 'Зарезервировано',
        ]
        df = df.groupby(group_cols, as_index=False).agg({
            'Лимит': 'sum',
            'Баланс': 'sum',
        })
        column_order = [
            'Бюджет', 'Статья расходов', 'Лимит', 'Баланс',
            'Зарезервировано', 'Юр. лицо', 'Подразделение',
            'Период', 'Дата', 'Активен',
        ]
        df = df[column_order]

    return df, list(set(unknown_depts)), list(set(unknown_articles))
