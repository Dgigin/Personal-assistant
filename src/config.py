# -*- coding: utf-8 -*-
"""
Конфигурация Flask-приложения.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Основные настройки приложения."""

    # Корневая директория проекта (где лежат app.py, templates/, src/)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Директория для пользовательских данных (логги, загрузки, сессии).
    # При установке через инсталлятор в Program Files использует %APPDATA%,
    # для портативной версии (запуск из папки проекта) — ту же папку.
    _is_in_program_files = 'PROGRAMFILES' in os.environ and 'Program Files' in BASE_DIR
    if _is_in_program_files:
        USER_DATA_DIR = os.path.join(os.environ.get('APPDATA', BASE_DIR), 'Excel Converter')
    else:
        USER_DATA_DIR = BASE_DIR

    # Директории
    PROFILES_DIR = os.path.join(USER_DATA_DIR, 'profiles')
    CONFIG_DIR = os.path.join(USER_DATA_DIR, 'config')
    UPLOAD_DIR = os.path.join(USER_DATA_DIR, 'uploads')
    LOG_DIR = os.path.join(USER_DATA_DIR, 'logs')

    # Пути к файлам (для health-check и моделей)
    TASKS_PATH = os.path.join(CONFIG_DIR, 'tasks.json')
    DEPARTMENTS_PATH = os.path.join(CONFIG_DIR, 'departments.json')
    ARTICLES_PATH = os.path.join(CONFIG_DIR, 'expense_articles.json')
    CHAT_DB_PATH = os.path.join(CONFIG_DIR, 'chat_history.db')

    # Настройки Flask
    # ВНИМАНИЕ: SECRET_KEY должен быть задан через переменную окружения!
    # Без уникального SECRET_KEY сессии Flask могут быть скомпрометированы.
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    UPLOAD_FOLDER = UPLOAD_DIR

    # DeepSeek API (загружается один раз при старте приложения)
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    # Настройки очистки загрузок
    UPLOAD_MAX_AGE_SECONDS = 3600  # 1 час

    # Аутентификация (HTTP Basic Auth)
    # Если AUTH_USERNAME и AUTH_PASSWORD не заданы — аутентификация отключена
    AUTH_USERNAME = os.getenv("AUTH_USERNAME", "")
    AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")

    # Настройки ротации логов
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB на файл
    LOG_BACKUP_COUNT = 5  # хранить 5 файлов

    # Интервал очистки uploads (в секундах)
    CLEANUP_INTERVAL_SECONDS = 30 * 60  # 30 минут

    # Таймаут неактивности сессии (в секундах)
    SESSION_TIMEOUT_SECONDS = 1800  # 30 минут

    # Автоотключение DeepSeek чата (в секундах)
    DEEPSEEK_AUTO_DISABLE_SECONDS = 5 * 3600  # 5 часов

    # Безопасность: HTTPS-only cookie для сессий
    # В продакшене с HTTPS установите SESSION_COOKIE_SECURE=True в .env
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 'yes')
