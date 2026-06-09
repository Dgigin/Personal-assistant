# -*- coding: utf-8 -*-
"""
Конфигурация pytest: фикстуры и вспомогательные функции.

ВАЖНО: отключаем аутентификацию для тестов ДО импорта app/config,
т.к. config.py вызывает load_dotenv() при импорте.
"""

import os
import sys

# Отключаем аутентификацию ДО импорта любых модулей проекта
os.environ['AUTH_USERNAME'] = ''
os.environ['AUTH_PASSWORD'] = ''

import uuid
import tempfile
import pytest
import pandas as pd
import numpy as np

# Добавляем корень проекта в sys.path для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app as _create_app


def create_test_excel(tmpdir: str, filename: str = 'test.xlsx') -> str:
    """
    Создаёт тестовый Excel-файл с заранее известными данными для тестов.

    Таблица:
    | Город  | Месяц | Продажи | Кол-во |
    |--------|-------|---------|--------|
    | Москва | Янв   | 100     | 10     |
    | Москва | Фев   | 150     | 15     |
    | СПб    | Янв   | 200     | 20     |
    | СПб    | Фев   | 250     | 25     |
    | Москва | Мар   | 120     | 12     |
    | СПб    | Апр   | 180     | 18     |

    :param tmpdir: Путь к временной директории
    :param filename: Имя файла
    :return: Полный путь к созданному файлу
    """
    filepath = os.path.join(tmpdir, filename)
    df = pd.DataFrame({
        'Город': ['Москва', 'Москва', 'СПб', 'СПб', 'Москва', 'СПб'],
        'Месяц': ['Янв', 'Фев', 'Янв', 'Фев', 'Мар', 'Апр'],
        'Продажи': [100, 150, 200, 250, 120, 180],
        'Кол-во': [10, 15, 20, 25, 12, 18],
    })
    df.to_excel(filepath, index=False)
    return filepath


def create_test_excel_with_dates(tmpdir: str, filename: str = 'test_dates.xlsx') -> str:
    """
    Создаёт тестовый Excel-файл с датами для тестов декомпозиции.

    Таблица:
    | Дата       | Город | Сумма |
    |------------|-------|-------|
    | 2026-01-15 | A     | 100   |
    | 2026-02-20 | B     | 200   |
    | 2026-03-10 | A     | 150   |
    | 2026-01-25 | B     | 250   |
    | NaT        | A     | 50    |

    :param tmpdir: Путь к временной директории
    :param filename: Имя файла
    :return: Полный путь к созданному файлу
    """
    filepath = os.path.join(tmpdir, filename)
    df = pd.DataFrame({
        'Дата': pd.to_datetime(['2026-01-15', '2026-02-20', '2026-03-10', '2026-01-25', pd.NaT]),
        'Город': ['A', 'B', 'A', 'B', 'A'],
        'Сумма': [100, 200, 150, 250, 50],
    })
    df.to_excel(filepath, index=False)
    return filepath


def create_test_csv(tmpdir: str, filename: str = 'test.csv') -> str:
    """
    Создаёт тестовый CSV-файл с кодировкой UTF-8.

    :param tmpdir: Путь к временной директории
    :param filename: Имя файла
    :return: Полный путь к созданному файлу
    """
    filepath = os.path.join(tmpdir, filename)
    df = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Age': [25, 30, 35],
        'City': ['Moscow', 'SPb', 'Kazan'],
    })
    df.to_csv(filepath, index=False, encoding='utf-8')
    return filepath


@pytest.fixture
def app():
    """Flask-приложение для интеграционных тестов."""
    app = _create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    # Отключаем аутентификацию для тестов
    os.environ['AUTH_USERNAME'] = ''
    os.environ['AUTH_PASSWORD'] = ''
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def tmp_excel(tmpdir):
    """Фикстура: создаёт тестовый Excel-файл, возвращает его путь."""
    return create_test_excel(str(tmpdir))


@pytest.fixture
def tmp_excel_dates(tmpdir):
    """Фикстура: создаёт тестовый Excel-файл с датами, возвращает его путь."""
    return create_test_excel_with_dates(str(tmpdir))


@pytest.fixture
def tmp_csv(tmpdir):
    """Фикстура: создаёт тестовый CSV-файл, возвращает его путь."""
    return create_test_csv(str(tmpdir))
