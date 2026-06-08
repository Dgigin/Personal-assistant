# -*- coding: utf-8 -*-
"""Сборка update.zip для GitHub Release — только необходимые файлы.

ВНИМАНИЕ: Файлы с пользовательскими данными (config/tasks.json, config/departments.json,
profiles/*.json и т.д.) НЕ включаются в update.zip — они создаются при первом запуске
приложения или копируются из example-файлов.
"""
import zipfile
import os

BASE = os.path.dirname(os.path.abspath(__file__))

FILES = [
    "app.py",
    "run.bat",
    "version.json",
    "requirements.txt",
    "install_deps.bat",
    # src — все .py файлы рекурсивно
    "src/",
    # templates
    "templates/index.html",
    # example-файлы конфигов (без реальных данных)
    "config/departments.json.example",
    "config/expense_articles.json.example",
    "config/tasks.json.example",
    # example-файл профиля
    "profiles/example.json",
]


def collect_files(base_dir):
    """Рекурсивно собираем .py файлы из src/, .json из config/ и profiles/."""
    files_to_zip = []

    for entry in FILES:
        path = os.path.join(base_dir, entry)
        if entry.endswith("/"):
            # Директория — собираем все файлы внутри
            for root, dirs, fnames in os.walk(path):
                # Пропускаем __pycache__
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fname in fnames:
                    fpath = os.path.join(root, fname)
                    arcname = os.path.relpath(fpath, base_dir)
                    files_to_zip.append((fpath, arcname))
        else:
            # Конкретный файл
            if os.path.exists(path):
                arcname = os.path.relpath(path, base_dir)
                files_to_zip.append((path, arcname))
            else:
                print(f"  [!] Пропущен (не найден): {entry}")

    return files_to_zip


def main():
    print("[*] Сборка update.zip...")
    zip_path = os.path.join(BASE, "update.zip")

    files = collect_files(BASE)
    print(f"  Найдено {len(files)} файлов")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for fpath, arcname in files:
            z.write(fpath, arcname)

    size_kb = os.path.getsize(zip_path) / 1024
    print(f"[OK] update.zip создан: {zip_path} ({size_kb:.1f} KB)")

    # Список файлов
    print("\n  Содержимое:")
    with zipfile.ZipFile(zip_path, "r") as z:
        for n in sorted(z.namelist()):
            print(f"    {n}")


if __name__ == "__main__":
    main()
