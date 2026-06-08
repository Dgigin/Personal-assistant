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
    _data_dir = os.path.join(os.environ.get('APPDATA', _PROJECT_ROOT), 'Personal Assistant')
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

    # Токен для доступа к приватному репозиторию
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
        logger.info("Используется GITHUB_TOKEN для авторизации")

    try:
        logger.info(f"Проверка обновлений: {api_url}")
        resp = requests.get(api_url, headers=headers, timeout=15)
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

        # Ищем архив (zip, 7z) в assets
        download_url = ""
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".zip") or name.endswith(".7z"):
                download_url = asset.get("browser_download_url", "")
                break

        # Если архив не найден, используем source code archive
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


def _create_apply_script(project_root: str, python_cmd: str = "", app_path: str = "") -> str:
    """
    Создаёт apply_update.py — скрипт для распаковки обновления через Python zipfile.
    После распаковки запускает app.py через subprocess.Popen.
    Возвращает путь к созданному скрипту.
    """
    script_path = os.path.join(project_root, "apply_update.py")
    # Экранируем обратные слеши, чтобы f-строка ниже не интерпретировала
    # \a, \P и т.д. как escape-последовательности
    python = (python_cmd or "python").replace("\\", "\\\\")
    app = (app_path or os.path.join(project_root, "app.py")).replace("\\", "\\\\")

    script_content = f'''# -*- coding: utf-8 -*-
"""Автоматически создан модулем updater.py — распаковка обновления и запуск приложения."""
import zipfile
import os
import shutil
import sys
import subprocess


def main():
    if len(sys.argv) < 3:
        print("[!] Недостаточно аргументов: apply_update.py <zip_path> <target_dir>")
        sys.exit(1)

    zip_path = sys.argv[1]
    target_dir = sys.argv[2]

    # Нейтрализуем update.bat: Windows не может удалить запущенный batch-файл
    # Перезаписываем его пустым содержимым, чтобы избежать ошибки
    # "The batch file cannot be found" от del "%~f0" в старых версиях update.bat
    update_bat_path = os.path.join(target_dir, "update.bat")
    try:
        with open(update_bat_path, "w") as f:
            f.write("@exit /b 0\\r\\n")
    except OSError:
        pass

    if not os.path.exists(zip_path):
        print(f"[!] Архив не найден: {{zip_path}}")
        sys.exit(1)

    print("[*] Распаковка обновления...")

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()

        # Определяем, есть ли вложенная папка (GitHub добавляет repo-branch)
        top_dirs = set()
        for n in names:
            parts = n.split("/")
            if len(parts) > 1 and parts[0]:
                top_dirs.add(parts[0])

        # Распаковываем
        z.extractall(target_dir)

        # Если файлы в подпапке — перемещаем на уровень выше
        for d in top_dirs:
            dp = os.path.join(target_dir, d)
            app_py = os.path.join(dp, "app.py")
            if os.path.exists(app_py):
                print(f"[*] Перемещение файлов из {{d}}/...")
                for fn in os.listdir(dp):
                    if fn in ("update.bat", "apply_update.py"):
                        continue
                    src = os.path.join(dp, fn)
                    dst = os.path.join(target_dir, fn)
                    if os.path.isdir(src):
                        if os.path.exists(dst):
                            shutil.copytree(src, dst, dirs_exist_ok=True)
                        else:
                            shutil.copytree(src, dst)
                    else:
                        shutil.move(src, dst)
                shutil.rmtree(dp)

    # Удаляем архив
    try:
        os.remove(zip_path)
        print("[*] Архив удалён")
    except OSError:
        pass

    # Удаляем флаг pending
    flag_path = os.path.join(target_dir, "update_pending.flag")
    if os.path.exists(flag_path):
        try:
            os.remove(flag_path)
        except OSError:
            pass

    # Удаляем сам apply_update.py
    try:
        os.remove(__file__)
    except OSError:
        pass

    # Удаляем update.bat окончательно (на случай, если перезапись его не очистила)
    if os.path.exists(update_bat_path):
        try:
            os.remove(update_bat_path)
        except OSError:
            pass

    print("[OK] Обновление установлено")

    # Запускаем приложение через subprocess (надёжнее, чем start в batch)
    python_exe = "{python}"
    app_script = "{app}"
    print("Запуск приложения...")
    try:
        subprocess.Popen([python_exe, app_script])
    except OSError as e:
        print(f"[!] Ошибка запуска приложения: {{e}}")
        sys.exit(1)


if __name__ == "__main__":
    main()
'''
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    return script_path


def install_update(zip_path: str) -> bool:
    """
    Устанавливает обновление: создаёт apply_update.py и update.bat,
    которые после рестарта распаковывают архив поверх текущей директории.
    apply_update.py сам нейтрализует старый update.bat и запускает app.py.
    Возвращает True, если подготовка к обновлению прошла успешно.
    """
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        target_dir = project_root

        # Определяем команду Python и путь к app.py
        python_cmd = sys.executable or "python"
        app_path = os.path.join(project_root, "app.py")

        # Создаём apply_update.py (передаём python_cmd и app_path для запуска после распаковки)
        apply_script = _create_apply_script(project_root, python_cmd, app_path)

        # Создаём update.bat — только запуск apply_update.py.
        # Вся логика (удаление update.bat, запуск app.py) — в apply_update.py.
        update_bat_path = os.path.join(project_root, "update.bat")

        bat_content = f"""@echo off
chcp 65001 > nul
echo Обновление Personal Assistant...
echo.

:: Ждём 3 секунды, чтобы сервер успел остановиться
ping 127.0.0.1 -n 4 > nul

:: Распаковываем обновление через Python
echo Распаковка обновления...
"{python_cmd}" "{apply_script}" "{zip_path}" "{target_dir}"

exit /b 0
"""
        with open(update_bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # Создаём флаг pending-обновления
        with open(PENDING_FLAG, "w", encoding="utf-8") as f:
            f.write("ready")

        logger.info(f"update.bat создан: {update_bat_path}")
        logger.info(f"apply_update.py создан: {apply_script}")
        return True

    except IOError as e:
        logger.error(f"Ошибка создания скриптов обновления: {e}")
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
