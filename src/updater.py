# -*- coding: utf-8 -*-
"""
Модуль проверки, скачивания и установки обновлений.
Использует GitHub Releases для распространения обновлений.
"""

import os
import json
import shutil
import tempfile
import zipfile
import logging
import time
import sys
from typing import Optional, Dict, Any
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Если приложение установлено в Program Files — используем %APPDATA% для временных файлов
_is_in_program_files = 'PROGRAMFILES' in os.environ and 'Program Files' in _PROJECT_ROOT
if _is_in_program_files:
    _data_dir = os.path.join(os.environ.get('APPDATA', _PROJECT_ROOT), 'Excel Converter')
else:
    _data_dir = _PROJECT_ROOT

# Путь к файлу версии относительно корня проекта
VERSION_FILE = os.path.join(_PROJECT_ROOT, "version.json")
# Временная папка для скачивания обновлений (в %APPDATA% если установлено в Program Files)
UPDATE_DIR = os.path.join(_data_dir, "temp", "update")
# Флаг pending-обновления
PENDING_FLAG = os.path.join(_PROJECT_ROOT, "update_pending.flag")


def get_current_version() -> str:
    """
    Читает текущую версию из version.json.
    Если файла нет или он повреждён, возвращает '0.0.0'.
    """
    try:
        if not os.path.exists(VERSION_FILE):
            logger.warning(f"Файл версии не найден: {VERSION_FILE}")
            return "0.0.0"
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version", "0.0.0")
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Ошибка чтения version.json: {e}")
        return "0.0.0"


def get_github_repo() -> str:
    """
    Читает название репозитория из version.json.
    """
    try:
        if not os.path.exists(VERSION_FILE):
            return ""
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("github_repo", "")
    except (json.JSONDecodeError, IOError):
        return ""


def _parse_version(version_str: str) -> tuple:
    """Парсит строку версии в кортеж для сравнения."""
    try:
        parts = version_str.replace("v", "").split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def check_for_update() -> Optional[Dict[str, Any]]:
    """
    Проверяет наличие обновления через GitHub Releases API.
    Возвращает словарь с информацией о релизе или None, если обновлений нет.

    Возвращаемый словарь:
    {
        "has_update": bool,
        "current_version": str,
        "latest_version": str,
        "download_url": str,
        "changelog": str,
        "published_at": str
    }
    """
    repo = get_github_repo()
    if not repo:
        logger.warning("Репозиторий GitHub не указан в version.json")
        return None

    current = get_current_version()
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"

    try:
        logger.info(f"Проверка обновлений: {api_url}")
        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        latest_tag = data.get("tag_name", "")  # Например "v1.2.0"
        latest_version = latest_tag.lstrip("v")

        # Сравниваем версии
        if _parse_version(latest_version) <= _parse_version(current):
            logger.info(f"Текущая версия {current} актуальна (последняя: {latest_version})")
            return {
                "has_update": False,
                "current_version": current,
                "latest_version": latest_version,
                "download_url": "",
                "changelog": "",
                "published_at": ""
            }

        # Ищем zip-архив в assets
        download_url = ""
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".zip"):
                download_url = asset.get("browser_download_url", "")
                break

        # Если zip не найден, используем source code archive
        if not download_url:
            download_url = data.get("zipball_url", "")

        changelog = data.get("body", "")
        published_at = data.get("published_at", "")

        logger.info(f"Доступно обновление: {current} -> {latest_version}")
        return {
            "has_update": True,
            "current_version": current,
            "latest_version": latest_version,
            "download_url": download_url,
            "changelog": changelog[:2000] if changelog else "",  # Ограничиваем длину
            "published_at": published_at
        }

    except requests.exceptions.Timeout:
        logger.error("Таймаут при проверке обновлений")
        return {
            "has_update": False,
            "current_version": current,
            "latest_version": current,
            "download_url": "",
            "changelog": "",
            "published_at": "",
            "error": "Превышено время ожидания. Проверьте подключение к интернету."
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при проверке обновлений: {e}")
        return {
            "has_update": False,
            "current_version": current,
            "latest_version": current,
            "download_url": "",
            "changelog": "",
            "published_at": "",
            "error": f"Ошибка сети: {e}"
        }
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Ошибка парсинга ответа GitHub API: {e}")
        return None


def download_update(download_url: str, progress_callback=None) -> Optional[str]:
    """
    Скачивает ZIP-архив обновления.
    Возвращает путь к скачанному файлу или None при ошибке.
    progress_callback(downloaded_bytes, total_bytes) — опциональный callback прогресса.
    """
    try:
        # Создаём временную папку для обновлений
        if os.path.exists(UPDATE_DIR):
            shutil.rmtree(UPDATE_DIR)
        os.makedirs(UPDATE_DIR, exist_ok=True)

        # Путь для сохранения ZIP
        zip_path = os.path.join(UPDATE_DIR, "update.zip")

        logger.info(f"Скачивание обновления: {download_url}")
        resp = requests.get(download_url, stream=True, timeout=60)
        resp.raise_for_status()

        # Определяем общий размер
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)

        logger.info(f"Обновление скачано: {zip_path} ({downloaded} байт)")
        return zip_path

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка скачивания обновления: {e}")
        return None
    except IOError as e:
        logger.error(f"Ошибка записи файла обновления: {e}")
        return None


def install_update(zip_path: str) -> bool:
    """
    Устанавливает обновление: создаёт update.bat, который после рестарта
    распаковывает архив поверх текущей директории.
    Возвращает True, если подготовка к обновлению прошла успешно.
    """
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        target_dir = project_root

        # Определяем команду Python и путь к app.py
        python_cmd = sys.executable or "python"
        app_path = os.path.join(project_root, "app.py")

        # Создаём update.bat
        update_bat_path = os.path.join(project_root, "update.bat")

        bat_content = f"""@echo off
chcp 65001 > nul
echo Обновление Excel Converter...
echo.

:: Ждём 3 секунды, чтобы сервер успел остановиться
ping 127.0.0.1 -n 4 > nul

:: Распаковываем обновление
echo Распаковка обновления...
if exist "{zip_path}" (
    tar -xf "{zip_path}" -C "{target_dir}" 2>nul
    if errorlevel 1 (
        :: Если tar недоступен, используем PowerShell
        powershell -command "Expand-Archive -Path '{zip_path}' -DestinationPath '{target_dir}' -Force"
    )
)

:: Если архив содержал вложенную папку (обычно repo-branch), перемещаем содержимое
for /d %%i in ("{target_dir}\\*") do (
    if exist "%%i\\app.py" (
        echo Перемещение файлов из вложенной папки...
        xcopy "%%i\\*" "{target_dir}\\" /E /Y
        rmdir /S /Q "%%i"
    )
)

:: Обновляем version.json, если новый архив содержал обновлённую версию
:: (файл уже распакован поверх)

:: Удаляем временные файлы
if exist "{zip_path}" del "{zip_path}"
if exist "{target_dir}\\update_pending.flag" del "{target_dir}\\update_pending.flag"

:: Удаляем сам update.bat
del "%~f0"

:: Запускаем приложение
echo Запуск приложения...
start "" "{python_cmd}" "{app_path}"

exit /b 0
"""
        with open(update_bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # Создаём флаг pending-обновления (для информирования UI)
        with open(PENDING_FLAG, "w", encoding="utf-8") as f:
            f.write("ready")

        logger.info(f"update.bat создан: {update_bat_path}")
        return True

    except IOError as e:
        logger.error(f"Ошибка создания update.bat: {e}")
        return False


def check_pending_update() -> bool:
    """
    Проверяет при запуске, есть ли незавершённое обновление.
    Удаляет мусорные файлы, если обновление было прервано.
    Возвращает True, если обновление было завершено (т.е. флаг существует).
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pending_flag = os.path.join(project_root, "update_pending.flag")
    update_bat = os.path.join(project_root, "update.bat")
    update_zip = os.path.join(project_root, "temp", "update", "update.zip")

    # Сначала проверяем version.json — если он изменился, обновление уже применилось
    # Флаг может остаться, если update.bat не успел его удалить (редкий случай)

    cleaned = False

    if os.path.exists(pending_flag):
        try:
            # Проверяем, не применилось ли уже обновление
            # Если update.bat уже отработал, флаг должен был удалиться
            logger.info("Обнаружен флаг pending-обновления. Проверяем состояние...")
            # Просто удаляем флаг — update.bat сам удалит себя при следующем запуске
            os.remove(pending_flag)
            cleaned = True
        except OSError as e:
            logger.warning(f"Не удалось удалить флаг pending: {e}")

    # Чистим старые update.bat, если они остались (например, от прерванного обновления)
    if os.path.exists(update_bat):
        try:
            os.remove(update_bat)
            logger.info("Удалён старый update.bat")
            cleaned = True
        except OSError as e:
            logger.warning(f"Не удалось удалить update.bat: {e}")

    # Чистим старые zip-архивы
    if os.path.exists(update_zip):
        try:
            os.remove(update_zip)
            cleaned = True
        except OSError:
            pass

    update_dir = os.path.dirname(update_zip) if update_zip else ""
    if update_dir and os.path.exists(update_dir):
        try:
            if not os.listdir(update_dir):
                os.rmdir(update_dir)
        except OSError:
            pass

    return cleaned


def update_current_version(new_version: str) -> bool:
    """
    Обновляет версию в version.json после успешного обновления.
    """
    try:
        if not os.path.exists(VERSION_FILE):
            return False
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["version"] = new_version
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Версия обновлена: {new_version}")
        return True
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Ошибка обновления version.json: {e}")
        return False
