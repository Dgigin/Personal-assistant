# -*- coding: utf-8 -*-
"""
Модуль аутентификации для Flask-приложения.

Сессионная аутентификация (Flask session + куки).
Если AUTH_USERNAME и AUTH_PASSWORD не заданы в .env — аутентификация отключена.
Автоматический выход при 10 минутах неактивности.
"""

import time
import logging
from flask import session, jsonify
from .config import Config

logger = logging.getLogger(__name__)


def is_auth_enabled() -> bool:
    """Проверяет, включена ли аутентификация (заданы ли credentials в .env)."""
    return bool(Config.AUTH_USERNAME and Config.AUTH_PASSWORD)


def login_user(username: str, password: str) -> bool:
    """
    Проверяет логин/пароль и при успехе записывает данные в сессию.
    Возвращает True при успешном входе.
    """
    if not is_auth_enabled():
        return True
    if username == Config.AUTH_USERNAME and password == Config.AUTH_PASSWORD:
        session.permanent = True
        session['authenticated'] = True
        session['username'] = username
        session['last_activity'] = time.time()
        logger.info('Пользователь %s вошёл в систему', username)
        return True
    return False


def logout_user() -> None:
    """Очищает сессию пользователя."""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info('Пользователь %s вышел из системы', username)


def check_session() -> bool:
    """
    Проверяет, аутентифицирован ли текущий пользователь.
    Если прошло более SESSION_TIMEOUT_SECONDS бездействия — очищает сессию.
    Возвращает True, если сессия валидна.
    """
    if not is_auth_enabled():
        return True

    if not session.get('authenticated'):
        return False

    last_activity = session.get('last_activity', 0)
    elapsed = time.time() - last_activity

    if elapsed > Config.SESSION_TIMEOUT_SECONDS:
        logger.info(
            'Сессия истекла по таймауту неактивности (%.0f сек > %d сек)',
            elapsed, Config.SESSION_TIMEOUT_SECONDS,
        )
        session.clear()
        return False

    # Обновляем время последней активности
    session['last_activity'] = time.time()
    return True


def unauthorized_response():
    """Возвращает JSON-ответ для 401 Unauthorized (без WWW-Authenticate)."""
    return jsonify({
        'error': 'Доступ запрещён. Требуется аутентификация.',
        'auth_required': True,
    }), 401
