# -*- coding: utf-8 -*-
"""
REST-маршруты для DeepSeek чата:
- /api/conversations (CRUD)
- /api/chat (streaming)
- /upload_chat_file (загрузка файлов в чат)
"""

import json
import os
import time

from flask import Blueprint, request, jsonify, Response, session

from ..config import Config
from ..models.chat_db import (
    init_db,
    get_conversations,
    create_conversation,
    get_messages,
    add_message,
    delete_conversation,
    rename_conversation,
)
from ..services.chat_service import stream_chat_completion
from ..utils.file_utils import (
    allowed_file,
    extract_text_from_txt,
    safe_remove,
    generate_temp_path,
)

chat_bp = Blueprint('chat', __name__)


def _get_config_dir():
    return Config.CONFIG_DIR


def _get_upload_dir():
    return Config.UPLOAD_DIR


# ==================== ЗАГРУЗКА ФАЙЛОВ ====================

@chat_bp.route('/upload_chat_file', methods=['POST'])
def upload_chat_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Неподдерживаемый формат. Поддерживаются: .txt, .md'}), 400

    upload_dir = _get_upload_dir()
    temp_path = generate_temp_path(upload_dir, prefix="chat_", suffix=f"_{file.filename}")
    file.save(temp_path)

    try:
        file_text = extract_text_from_txt(temp_path)
        if not file_text:
            file_text = "Файл пуст."
        return jsonify({'text': file_text, 'filename': file.filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        safe_remove(temp_path)


# ==================== ДИАЛОГИ ====================

@chat_bp.route('/api/conversations', methods=['GET'])
def api_get_conversations():
    config_dir = _get_config_dir()
    return jsonify(get_conversations(config_dir))


@chat_bp.route('/api/conversations', methods=['POST'])
def api_create_conversation():
    data = request.get_json()
    title = data.get('title', 'Новый диалог')
    config_dir = _get_config_dir()
    conv = create_conversation(config_dir, title)
    return jsonify(conv)


@chat_bp.route('/api/conversations/<conv_id>', methods=['PUT'])
def api_rename_conversation(conv_id):
    data = request.get_json()
    new_title = data.get('title', '').strip()
    if not new_title:
        return jsonify({'error': 'Название не может быть пустым'}), 400
    config_dir = _get_config_dir()
    rename_conversation(config_dir, conv_id, new_title)
    return jsonify({'success': True})


@chat_bp.route('/api/conversations/<conv_id>', methods=['DELETE'])
def api_delete_conversation(conv_id):
    config_dir = _get_config_dir()
    delete_conversation(config_dir, conv_id)
    return jsonify({'success': True})


# ==================== СООБЩЕНИЯ ====================

@chat_bp.route('/api/conversations/<conv_id>/messages', methods=['GET'])
def api_get_messages(conv_id):
    config_dir = _get_config_dir()
    return jsonify(get_messages(config_dir, conv_id))


# ==================== ЧАТ (STREAMING) ====================

# Максимальное количество сообщений из истории, отправляемых в DeepSeek API
# (чтобы избежать превышения лимита токенов)
MAX_HISTORY_MESSAGES = 50


@chat_bp.route('/api/chat', methods=['POST'])
def chat_completion():
    # Проверка, включён ли DeepSeek чат
    deepseek_enabled = session.get('deepseek_enabled', False)
    if not deepseek_enabled:
        return jsonify({
            'error': 'DeepSeek чат выключен. Включите его на вкладке чата.',
        }), 403

    # Проверка автоотключения по таймауту
    enabled_at = session.get('deepseek_enabled_at', 0)
    if enabled_at:
        elapsed = time.time() - enabled_at
        if elapsed > Config.DEEPSEEK_AUTO_DISABLE_SECONDS:
            session['deepseek_enabled'] = False
            session.pop('deepseek_enabled_at', None)
            return jsonify({
                'error': 'Время работы DeepSeek чата истекло (5 часов). Включите снова.',
            }), 403

    data = request.get_json()
    conv_id = data.get('conversation_id')
    user_message = data.get('message')
    file_text = data.get('file_text', '')

    if not conv_id or not user_message:
        return jsonify({'error': 'Не хватает данных'}), 400

    config_dir = _get_config_dir()

    # Сохраняем сообщение пользователя
    add_message(config_dir, conv_id, 'user', user_message)

    # Формируем полное сообщение, если загружен файл
    if file_text:
        truncated = file_text[:5000]
        full_message = f"Вопрос: {user_message}\n\nСодержимое загруженного файла:\n{truncated}"
    else:
        full_message = user_message

    # История сообщений — усекаем до последних MAX_HISTORY_MESSAGES
    history = get_messages(config_dir, conv_id)
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    messages_for_api = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
    ]
    messages_for_api.append({"role": "user", "content": full_message})

    api_key = Config.DEEPSEEK_API_KEY
    api_url = "https://api.deepseek.com/v1/chat/completions"

    def generate():
        full_response = ""
        try:
            for event in stream_chat_completion(api_key, api_url, messages_for_api):
                full_response += event  # накапливаем
                yield event
        finally:
            # Сохраняем ответ ассистента (из последнего chunk)
            if full_response:
                # Извлекаем чистый текст из событий
                import json as json_mod
                response_text = ""
                for part in full_response.split('\n\n'):
                    if part.startswith('data: '):
                        try:
                            chunk_data = json_mod.loads(part[6:])
                            if 'content' in chunk_data:
                                response_text += chunk_data['content']
                        except Exception:
                            pass
                if response_text:
                    add_message(config_dir, conv_id, 'assistant', response_text)

    return Response(generate(), mimetype='text/event-stream')


# ==================== OCR (РАСПОЗНАВАНИЕ ИЗОБРАЖЕНИЙ) ====================

import hashlib
import base64 as b64_mod

# Временное хранилище file_id -> temp_path (для download_temp_file)
_temp_files: dict = {}


# Максимальный размер base64 изображения для OCR (10 MB после декодирования ~ 14 MB в base64)
MAX_OCR_IMAGE_SIZE = 14 * 1024 * 1024  # 14 MB (base64)


@chat_bp.route('/api/chat/ocr', methods=['POST'])
def ocr_image_endpoint():
    """
    Принимает изображение (base64), запускает EasyOCR.
    Возвращает распознанный текст и, если найдена таблица, JSON-массив.
    """
    data = request.get_json()
    image_base64 = data.get('image_base64', '')
    image_mime = data.get('image_mime', 'image/png')

    if not image_base64:
        return jsonify({'error': 'Изображение не передано'}), 400

    # Ограничение размера base64 (защита от DoS)
    if len(image_base64) > MAX_OCR_IMAGE_SIZE:
        return jsonify({
            'error': f'Изображение слишком большое. Максимум {MAX_OCR_IMAGE_SIZE // (1024 * 1024)} MB.'
        }), 413

    temp_path = None
    try:
        image_data = b64_mod.b64decode(image_base64)
        ext = '.png' if 'png' in image_mime else '.jpg'
        temp_path = generate_temp_path(Config.UPLOAD_DIR, prefix="ocr_", suffix=ext)
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
        with open(temp_path, 'wb') as f:
            f.write(image_data)

        from ..services.ocr_service import extract_table_from_image
        result = extract_table_from_image(temp_path)

        return jsonify({
            'success': result.get('success', False),
            'raw_text': result['raw_text'],
            'table_text': result['table_text'],
            'table_json': result['table_json'],
            'is_table': result['is_table'],
            'rows_count': result['rows_count'],
            'items_count': result['items_count'],
        })

    except Exception as e:
        return jsonify({'error': f'Oшибка OCR: {str(e)}'}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            safe_remove(temp_path)


@chat_bp.route('/api/chat/convert_table', methods=['POST'])
def convert_table_to_xlsx():
    """
    Принимает JSON-массив объектов (таблицу), генерирует .xlsx.
    Возвращает file_id для скачивания через /convert/download_temp/<file_id>.
    """
    data = request.get_json()
    table_data = data.get('data', [])
    filename = data.get('filename', 'table.xlsx')

    if not table_data or not isinstance(table_data, list) or len(table_data) == 0:
        return jsonify({'error': 'Некорректные данные таблицы'}), 400

    temp_path = None
    try:
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)

        # Используем ту же схему именования, что и в converter_routes.download_temp_file
        file_id = hashlib.md5(str(hashlib.md5(str(table_data).encode()).hexdigest()).encode()).hexdigest()[:12]
        temp_path = os.path.join(Config.UPLOAD_DIR, f'temp_result_{file_id}.xlsx')

        from ..utils.file_utils import save_json_as_xlsx
        save_json_as_xlsx(table_data, temp_path)

        return jsonify({
            'file_id': file_id,
            'filename': filename,
            'download_url': f'/convert/download_temp/{file_id}'
        })
    except Exception as e:
        return jsonify({'error': f'Oшибка генерации .xlsx: {str(e)}'}), 500
