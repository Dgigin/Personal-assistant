# -*- coding: utf-8 -*-
"""
Сервис для взаимодействия с DeepSeek API (streaming chat).
"""

import json
from typing import List, Dict, Any, Generator

import requests


def stream_chat_completion(
    api_key: str,
    api_url: str,
    messages: List[Dict[str, str]],
    model: str = "deepseek-chat",
) -> Generator[str, None, str]:
    """
    Отправляет запрос к DeepSeek API и стримит ответ.

    :param api_key: API-ключ DeepSeek
    :param api_url: URL эндпоинта API
    :param messages: История сообщений в формате [{"role": ..., "content": ...}]
    :param model: Название модели
    :yield: Строки с контентом (data: ...)
    :return: Полный накопленный текст ответа
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    full_response = ""
    try:
        response = requests.post(api_url, json=payload, headers=headers, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        if 'content' in delta:
                            content = delta['content']
                            full_response += content
                            yield f"data: {json.dumps({'content': content})}\n\n"
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return  # завершаем генератор после ошибки

    return full_response
