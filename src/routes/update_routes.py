# -*- coding: utf-8 -*-
"""
Blueprint с эндпоинтами для проверки и применения обновлений.
"""

import os
import threading
import logging
from flask import Blueprint, jsonify, request

from ..updater import (
    check_for_update,
    download_update,
    install_update,
    get_current_version
)

logger = logging.getLogger(__name__)

update_bp = Blueprint("update", __name__)

# Глобальное состояние обновления для отслеживания прогресса
_update_state = {
    "status": "idle",  # idle | downloading | ready | error
    "progress": 0,
    "total": 0,
    "latest_version": "",
    "error": "",
    "download_url": ""
}


@update_bp.route("/api/version", methods=["GET"])
def api_version():
    """
    GET /api/version
    Быстрое получение текущей версии приложения (без обращения к GitHub).
    """
    return jsonify({
        "version": get_current_version()
    }), 200


@update_bp.route("/api/check_update", methods=["GET"])
def api_check_update():
    """
    GET /api/check_update
    Проверяет наличие обновления через GitHub Releases API.

    Ответ:
    {
        "has_update": bool,
        "current_version": str,
        "latest_version": str,
        "download_url": str,
        "changelog": str,
        "published_at": str,
        "error": str (опционально)
    }
    """
    result = check_for_update()
    if result is None:
        return jsonify({
            "has_update": False,
            "current_version": get_current_version(),
            "latest_version": "",
            "error": "Не удалось проверить обновления"
        }), 200

    # Обновляем глобальное состояние
    _update_state["latest_version"] = result.get("latest_version", "")
    _update_state["download_url"] = result.get("download_url", "")

    return jsonify(result), 200


@update_bp.route("/api/check_update/status", methods=["GET"])
def api_update_status():
    """
    GET /api/check_update/status
    Возвращает текущий статус процесса обновления.

    Ответ:
    {
        "status": "idle" | "downloading" | "ready" | "error",
        "progress": int,
        "total": int,
        "latest_version": str,
        "error": str
    }
    """
    return jsonify(_update_state), 200


@update_bp.route("/api/apply_update", methods=["POST"])
def api_apply_update():
    """
    POST /api/apply_update
    Начинает процесс обновления: скачивает и подготавливает установку.

    Тело запроса (JSON):
    {
        "download_url": "https://..." (опционально, если не указан — берётся из состояния)
    }

    Ответ:
    {
        "success": bool,
        "message": str,
        "status": str
    }
    """
    global _update_state

    data = request.get_json(silent=True) or {}
    download_url = data.get("download_url", _update_state.get("download_url", ""))

    if not download_url:
        return jsonify({
            "success": False,
            "message": "URL для скачивания не указан",
            "status": "error"
        }), 400

    if _update_state["status"] == "downloading":
        return jsonify({
            "success": False,
            "message": "Обновление уже скачивается",
            "status": "downloading"
        }), 409

    # Сбрасываем состояние
    _update_state["status"] = "downloading"
    _update_state["progress"] = 0
    _update_state["total"] = 0
    _update_state["error"] = ""

    def progress_callback(downloaded, total):
        _update_state["progress"] = downloaded
        _update_state["total"] = total

    def download_thread():
        global _update_state
        try:
            zip_path = download_update(download_url, progress_callback=progress_callback)
            if zip_path is None:
                _update_state["status"] = "error"
                _update_state["error"] = "Ошибка скачивания обновления"
                return

            # Устанавливаем обновление (создаём update.bat)
            success = install_update(zip_path)
            if success:
                _update_state["status"] = "ready"
                logger.info("Обновление готово к установке. Требуется перезапуск.")
            else:
                _update_state["status"] = "error"
                _update_state["error"] = "Ошибка подготовки обновления"

        except Exception as e:
            logger.exception("Ошибка в процессе обновления")
            _update_state["status"] = "error"
            _update_state["error"] = str(e)

    # Запускаем скачивание в фоновом потоке
    thread = threading.Thread(target=download_thread, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "message": "Начато скачивание обновления",
        "status": "downloading"
    }), 202


@update_bp.route("/api/apply_update/restart", methods=["POST"])
def api_restart_for_update():
    """
    POST /api/apply_update/restart
    Запускает update.bat и завершает текущий процесс сервера.
    Клиент должен быть готов к тому, что сервер перезапустится.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    update_bat = os.path.join(project_root, "update.bat")

    if not os.path.exists(update_bat):
        return jsonify({
            "success": False,
            "message": "Файл обновления (update.bat) не найден. Сначала выполните /api/apply_update."
        }), 400

    # Запускаем update.bat в фоне
    import subprocess
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", update_bat],
            shell=True,
            cwd=project_root
        )
        logger.info("update.bat запущен. Сервер завершает работу.")

        # Возвращаем ответ и завершаем процесс
        return jsonify({
            "success": True,
            "message": "Сервер перезапускается для применения обновления..."
        }), 200

    except Exception as e:
        logger.error(f"Ошибка запуска update.bat: {e}")
        return jsonify({
            "success": False,
            "message": f"Ошибка запуска обновления: {e}"
        }), 500
