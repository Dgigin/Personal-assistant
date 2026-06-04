# -*- coding: utf-8 -*-
"""
Скрипт создания .env из .env.example с генерацией уникального SECRET_KEY.

Запускается из install_deps.bat и run.bat при первой установке.
Если .env уже существует — ничего не делает.
"""

import os
import secrets


def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(project_root, '.env')
    example_path = os.path.join(project_root, '.env.example')

    # Если .env уже существует — не трогаем
    if os.path.exists(env_path):
        print('[*] .env уже существует, пропускаем')
        return

    if not os.path.exists(example_path):
        print('[!] .env.example не найден! Создаю .env вручную...')
        # Создаём минимальный .env с гостевыми данными
        new_key = secrets.token_hex(32)
        content = (
            "# DeepSeek API ключ для чата (опционально)\n"
            "# DEEPSEEK_API_KEY=sk-your-key-here\n"
            f"SECRET_KEY={new_key}\n"
            "AUTH_USERNAME=guest\n"
            "AUTH_PASSWORD=guest\n"
        )
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'[OK] .env создан с уникальным SECRET_KEY ({new_key[:8]}...)')
        return

    # Читаем .env.example
    with open(example_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Генерируем уникальный SECRET_KEY
    new_key = secrets.token_hex(32)

    # Заменяем плейсхолдер на сгенерированный ключ
    if '__GENERATE_ME__' in content:
        content = content.replace('__GENERATE_ME__', new_key)
        print(f'[OK] Сгенерирован уникальный SECRET_KEY ({new_key[:8]}...)')
    else:
        print('[*] Плейсхолдер __GENERATE_ME__ не найден, SECRET_KEY остаётся из шаблона')

    # Записываем .env
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'[OK] .env создан из .env.example')


if __name__ == '__main__':
    main()
