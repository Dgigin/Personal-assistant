# -*- coding: utf-8 -*-
"""
Личный помощник – гибкий конвертер Excel + блокнот задач + DeepSeek чат с ветками диалогов.

Точка входа в приложение.
"""

import os
import sys
import logging
import logging.handlers

from datetime import timedelta
from flask import Flask, jsonify, render_template, request, session
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf


from src.config import Config
from src.models.chat_db import init_db
from src.utils.file_utils import clean_old_uploads
from src.scheduler import (
    start_schedulers,
    cleanup_session_files_at_startup,
)
from src.routes.converter_routes import converter_bp
from src.routes.task_routes import task_bp
from src.routes.chat_routes import chat_bp
from src.routes.constructor_routes import constructor_bp
from src.routes.report_routes import report_bp
from src.routes.update_routes import update_bp
from src.updater import check_pending_update
import time
from src.auth import is_auth_enabled, login_user, logout_user, check_session, unauthorized_response

# ---------------------------------------------------------------------------
# Настройка лимитера запросов (in-memory)
# ---------------------------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri='memory://',
)


# ---------------------------------------------------------------------------
# Настройка логирования (консоль + файл с ротацией)
# ---------------------------------------------------------------------------
os.makedirs(Config.LOG_DIR, exist_ok=True)

_log_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# Файловый handler с ежедневной ротацией (макс 5 файлов)
_file_handler = logging.handlers.TimedRotatingFileHandler(
    os.path.join(Config.LOG_DIR, 'app.log'),
    when='midnight',
    interval=1,
    backupCount=Config.LOG_BACKUP_COUNT,
    encoding='utf-8',
)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(_log_formatter)

# Консольный handler
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_log_formatter)

# Корневой логгер
logging.basicConfig(
    level=logging.INFO,
    handlers=[_file_handler, _console_handler],
)

# Подавляем логи Werkzeug в консоли (оставляем в файле) — ERROR отсекает и development server warning
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Waitress пишет WARNING при глубине очереди задач 1-2 — для одного пользователя это норма,
# приглушаем до ERROR (реальные ошибки останутся)
logging.getLogger('waitress.queue').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Фабрика приложения Flask."""
    app = Flask(__name__)

    # Конфигурация
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    # Настройки Flask session (сервер-сайд, файловое хранилище)
    SESSION_DIR = os.path.join(Config.USER_DATA_DIR, 'flask_session')
    app.config.update(
        SESSION_TYPE='filesystem',
        SESSION_FILE_DIR=SESSION_DIR,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=Config.SESSION_COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        TEMPLATES_AUTO_RELOAD=True,
    )
    Session(app)

    # Проверка SECRET_KEY при старте
    if not Config.SECRET_KEY or Config.SECRET_KEY == '__GENERATE_ME__':
        import secrets
        app.secret_key = secrets.token_hex(32)
        logger.warning(
            'SECRET_KEY не задан. Сгенерирован временный ключ (%s...). '
            'Сессии будут действовать до перезапуска сервера. '
            'Для постоянного ключа задайте SECRET_KEY в .env',
            app.secret_key[:8]
        )

    # -----------------------------------------------------------------------
    # CSRF-защита (Flask-WTF)
    # -----------------------------------------------------------------------
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 час жизни токена
    app.config['WTF_CSRF_SSL_STRICT'] = False  # Не требовать HTTPS для Referrer
    app.config['WTF_CSRF_METHODS'] = ['POST', 'PUT', 'PATCH', 'DELETE']  # Явно указываем методы для CSRF-проверки
    csrf = CSRFProtect()

    # Исключаем из CSRF-защиты:
    # - эндпоинты обновления (фронтенд не шлёт CSRF-токен, сервер всё равно перезапустится)
    # - public эндпоинты, доступные до аутентификации
    csrf.exempt(update_bp)
    csrf.init_app(app)

    # -----------------------------------------------------------------------
    # Обработчик CSRF-ошибок (через errorhandler 400)
    # -----------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request_handler(e):
        """Если CSRF-токен отсутствует или невалиден — отдаём JSON."""
        # Проверяем, связана ли ошибка с CSRF
        csrf_error = getattr(e, 'description', None)
        if csrf_error and 'csrf' in str(csrf_error).lower():
            logger.warning('CSRF-ошибка: %s', csrf_error)
            return jsonify({
                'error': 'CSRF-токен отсутствует или истёк. Обновите страницу.',
                'csrf_required': True,
            }), 400
        # Обычная 400 ошибка
        return jsonify({'error': 'Bad request'}), 400

    # Создаём директории при старте

    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(Config.PROFILES_DIR, exist_ok=True)
    os.makedirs(Config.CONFIG_DIR, exist_ok=True)
    os.makedirs(Config.LOG_DIR, exist_ok=True)
    os.makedirs(SESSION_DIR, exist_ok=True)

    # Очищаем старые загруженные файлы при старте
    clean_old_uploads(Config.UPLOAD_DIR, Config.UPLOAD_MAX_AGE_SECONDS)

    # Очищаем все сессии при старте — после перезапуска сервера
    # требуется повторная авторизация
    cleanup_session_files_at_startup(SESSION_DIR)

    # Проверяем наличие незавершённого обновления при запуске
    check_pending_update()

    # Регистрируем Blueprint'ы
    app.register_blueprint(converter_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(constructor_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(update_bp)

    # -----------------------------------------------------------------------
    # Аутентификация (сессионная)
    # -----------------------------------------------------------------------
    if is_auth_enabled():
        logger.info('Аутентификация включена')
    else:
        logger.warning(
            'Аутентификация отключена! Задайте AUTH_USERNAME и AUTH_PASSWORD '
            'в .env для включения.'
        )

    # Эндпоинт для проверки статуса аутентификации (не защищён)
    @app.route('/api/auth_status')
    def auth_status():
        """Проверяет статус аутентификации без обновления last_activity.
        Это позволяет таймауту неактивности (10 мин) срабатывать корректно,
        даже если фронтенд шлёт keepalive-пинги каждые 5 минут."""
        auth_enabled = is_auth_enabled()
        if not auth_enabled:
            return jsonify({'auth_enabled': False, 'authenticated': True})

        # Проверяем сессию, но НЕ обновляем last_activity
        if not session.get('authenticated'):
            return jsonify({'auth_enabled': True, 'authenticated': False})

        last_activity = session.get('last_activity', 0)
        elapsed = time.time() - last_activity

        if elapsed > Config.SESSION_TIMEOUT_SECONDS:
            session.clear()
            logger.info(
                'Сессия истекла по таймауту неактивности (keepalive, %.0f сек > %d сек)',
                elapsed, Config.SESSION_TIMEOUT_SECONDS,
            )
            return jsonify({'auth_enabled': True, 'authenticated': False})

        # Не обновляем last_activity — пусть таймаут реально срабатывает
        return jsonify({'auth_enabled': True, 'authenticated': True})

    # Эндпоинт для входа (с ограничением: макс. 5 запросов в минуту)
    @app.route('/api/login', methods=['POST'])
    @limiter.limit("5/minute")
    def api_login():
        data = request.get_json() or {}
        username = data.get('username', '')
        password = data.get('password', '')
        if not is_auth_enabled():
            return jsonify({'success': True, 'auth_enabled': False})
        if login_user(username, password):
            return jsonify({'success': True, 'auth_enabled': True})
        return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401

    # Эндпоинт для выхода
    @app.route('/api/logout', methods=['POST'])
    def api_logout():
        logout_user()
        return jsonify({'success': True})

    # -----------------------------------------------------------------------
    # Защита всех маршрутов (сессионная аутентификация)
    # -----------------------------------------------------------------------
    @app.before_request
    def protect_routes():
        """Проверяет сессию перед каждым запросом.

        Исключения (без аутентификации):
        - /api/auth_status — проверка статуса авторизации
        - /api/login — эндпоинт для входа
        - /api/logout — эндпоинт для выхода
        - / — главная страница (index.html), чтобы JS мог показать модалку логина
        """
        if not is_auth_enabled():
            return None

        # Пропускаем маршруты, не требующие аутентификации
        if request.path in ('/', '/api/auth_status', '/api/login', '/api/logout',
                            '/api/csrf_token',
                            '/api/chat/status', '/api/chat/toggle',
                            '/api/version',
                            '/api/check_update', '/api/check_update/status',
                            '/api/apply_update', '/api/apply_update/restart'):
            return None


        # Проверяем сессию (автоматически обновляет last_activity)
        if not check_session():
            return unauthorized_response()
        return None

    # -----------------------------------------------------------------------
    # Заголовки безопасности
    # -----------------------------------------------------------------------
    @app.after_request
    def add_security_headers(response):
        # Запрет на MIME-sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Запрет на встраивание в iframe (защита от clickjacking)
        response.headers['X-Frame-Options'] = 'DENY'
        # Referrer Policy — не передавать URL
        response.headers['Referrer-Policy'] = 'no-referrer'
        # Content-Security-Policy (защита от XSS)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self' https://api.deepseek.com; "
            "font-src 'self'; "
            "form-action 'self'"
        )
        # Обновляем last_activity после завершения запроса, чтобы долгие
        # операции (загрузка/обработка файлов >30 мин) не обрывали сессию
        if is_auth_enabled() and session.get('authenticated'):
            # Не обновляем для исключённых из аутентификации маршрутов,
            # чтобы фоновый поллинг не сбрасывал таймер неактивности
            if request.path not in ('/', '/api/auth_status', '/api/login', '/api/logout',
                                    '/api/chat/status', '/api/chat/toggle',
                                    '/api/version',
                                    '/api/check_update', '/api/check_update/status',
                                    '/api/apply_update', '/api/apply_update/restart'):
                session['last_activity'] = time.time()
        return response

    # -----------------------------------------------------------------------
    # Инициализация SQLite для чата
    # -----------------------------------------------------------------------
    init_db(Config.CONFIG_DIR)

    # -----------------------------------------------------------------------
    # Запуск фоновых планировщиков (uploads, задачи, сессии)
    # -----------------------------------------------------------------------
    start_schedulers(
        upload_dir=Config.UPLOAD_DIR,
        upload_max_age_seconds=Config.UPLOAD_MAX_AGE_SECONDS,
        cleanup_interval_seconds=Config.CLEANUP_INTERVAL_SECONDS,
        session_dir=SESSION_DIR,
        config_dir=Config.CONFIG_DIR,
    )

    # -----------------------------------------------------------------------
    # Маршруты
    # -----------------------------------------------------------------------

    # Главная страница
    @app.route('/')
    def index():
        return render_template('index.html')

    # -----------------------------------------------------------------------
    # Управление DeepSeek чатом (вкл/выкл)
    # -----------------------------------------------------------------------
    @app.route('/api/chat/status', methods=['GET'])
    def chat_status():
        """Возвращает статус DeepSeek чата."""
        enabled = session.get('deepseek_enabled', False)
        enabled_at = session.get('deepseek_enabled_at', 0)

        # Проверка автоотключения
        if enabled and enabled_at:
            elapsed = time.time() - enabled_at
            if elapsed > Config.DEEPSEEK_AUTO_DISABLE_SECONDS:
                session['deepseek_enabled'] = False
                session.pop('deepseek_enabled_at', None)
                enabled = False
                logger.info('DeepSeek чат автоматически отключён (прошло %.0f сек)', elapsed)

        expires_at = enabled_at + Config.DEEPSEEK_AUTO_DISABLE_SECONDS if enabled else 0
        return jsonify({
            'enabled': enabled,
            'expires_at': expires_at,
            'remaining_seconds': max(0, expires_at - time.time()) if enabled else 0,
        })

    @app.route('/api/chat/toggle', methods=['POST'])
    def chat_toggle():
        """Включает или выключает DeepSeek чат."""
        data = request.get_json() or {}
        new_state = data.get('enabled', False)

        if new_state:
            session['deepseek_enabled'] = True
            session['deepseek_enabled_at'] = time.time()
            logger.info('DeepSeek чат включён пользователем')
        else:
            session['deepseek_enabled'] = False
            session.pop('deepseek_enabled_at', None)
            logger.info('DeepSeek чат выключен пользователем')

        return jsonify({'enabled': session.get('deepseek_enabled', False)})

    # Health-check эндпоинт
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    # -----------------------------------------------------------------------
    # CSRF-токен для фронтенда
    # -----------------------------------------------------------------------
    @app.route('/api/csrf_token', methods=['GET'])
    def get_csrf_token():
        """Возвращает CSRF-токен для фронтенда."""
        return jsonify({'csrf_token': generate_csrf()})

    return app



if __name__ == '__main__':
    application = create_app()
    logger.info('Сервер запущен на http://localhost:5000')
    # ВНИМАНИЕ: для продакшена используйте wsgi.py (waitress), а не app.py напрямую.
    # debug=True НЕ БЕЗОПАСЕН для продакшена — даёт доступ к Werkzeug debugger.
    application.run(debug=False, host='127.0.0.1', port=5000)
