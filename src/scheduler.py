# -*- coding: utf-8 -*-
"""
Модуль фоновых планировщиков APScheduler.

Содержит:
- Очистку старых загруженных файлов (uploads/)
- Архивацию выполненных задач
- Очистку устаревших файлов сессий Flask-Session
"""

import os
import logging
import atexit
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from src.models.tasks import load_tasks, save_tasks, archive_completed_tasks
from src.utils.file_utils import clean_old_uploads

logger = logging.getLogger(__name__)


def cleanup_session_files_at_startup(session_dir: str) -> None:
    """
    Удаляет все файлы сессий из директории flask_session при старте.
    После перезапуска сервера все старые сессии становятся невалидными,
    поэтому их можно безопасно удалить.
    """
    try:
        if not os.path.exists(session_dir):
            return
        for fname in os.listdir(session_dir):
            fpath = os.path.join(session_dir, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
        logger.info('Очищены файлы сессий при старте приложения')
    except Exception as e:
        logger.warning('Не удалось очистить файлы сессий: %s', e)


def _cleanup_old_session_files(session_dir: str, max_age_days: int = 7) -> None:
    """
    Периодическая очистка устаревших файлов сессий.
    Удаляет файлы сессий, которые не изменялись дольше max_age_days дней.
    """
    try:
        if not os.path.exists(session_dir):
            return
        now = datetime.now()
        count = 0
        for fname in os.listdir(session_dir):
            fpath = os.path.join(session_dir, fname)
            if os.path.isfile(fpath):
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if now - mtime > timedelta(days=max_age_days):
                    os.remove(fpath)
                    count += 1
        if count > 0:
            logger.info('Очищено %d устаревших файлов сессий (старше %d дней)', count, max_age_days)
    except Exception as e:
        logger.warning('Не удалось выполнить очистку сессий: %s', e)


def start_schedulers(
    upload_dir: str,
    upload_max_age_seconds: int,
    cleanup_interval_seconds: int,
    session_dir: str,
    config_dir: str,
) -> BackgroundScheduler:
    """
    Запускает все фоновые планировщики APScheduler.

    :param upload_dir: Путь к директории uploads
    :param upload_max_age_seconds: Макс. возраст файлов в uploads (сек)
    :param cleanup_interval_seconds: Интервал очистки uploads (сек)
    :param session_dir: Путь к директории flask_session
    :param config_dir: Путь к директории config (для задач)
    :return: Экземпляр BackgroundScheduler
    """
    # Приглушаем штатные логи APScheduler (добавление задач, старт, выполнение и т.п.)
    # Ошибки (WARNING/ERROR) продолжат выводиться
    logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)

    scheduler = BackgroundScheduler()

    errors = []

    # ------------------------------------------------------------------
    # 1. Планировщик очистки старых загруженных файлов
    # ------------------------------------------------------------------
    try:
        scheduler.add_job(
            func=lambda: clean_old_uploads(upload_dir, upload_max_age_seconds),
            trigger='interval',
            seconds=cleanup_interval_seconds,
            id='cleanup_uploads',
            name='Очистка старых загруженных файлов',
            replace_existing=True,
        )
    except Exception as e:
        errors.append(f'Очистка загруженных файлов: {e}')

    # ------------------------------------------------------------------
    # 2. Планировщик архивации выполненных задач
    # ------------------------------------------------------------------
    def _archive_job():
        try:
            tasks = load_tasks(config_dir)
            tasks = archive_completed_tasks(tasks)
            save_tasks(config_dir, tasks)
        except Exception as e:
            logger.error('Ошибка при фоновой архивации задач: %s', e)

    try:
        scheduler.add_job(
            func=_archive_job,
            trigger='interval',
            seconds=300,  # каждые 5 минут
            id='archive_tasks',
            name='Архивация выполненных задач',
            replace_existing=True,
        )
    except Exception as e:
        errors.append(f'Архивация задач: {e}')

    # ------------------------------------------------------------------
    # 3. Планировщик очистки устаревших файлов сессий
    #    Запускается каждые 6 часов, удаляет файлы старше 7 дней
    # ------------------------------------------------------------------
    try:
        scheduler.add_job(
            func=lambda: _cleanup_old_session_files(session_dir, max_age_days=7),
            trigger='interval',
            hours=6,
            id='cleanup_sessions',
            name='Очистка устаревших файлов сессий',
            replace_existing=True,
        )
    except Exception as e:
        errors.append(f'Очистка сессий: {e}')

    if errors:
        logger.warning(
            'Планировщики запущены с ошибками: %s',
            '; '.join(errors),
        )
    else:
        logger.info('Все планировщики успешно запущены')

    scheduler.start()

    # Корректная остановка планировщика при завершении приложения
    atexit.register(lambda: scheduler.shutdown(wait=False))

    return scheduler
