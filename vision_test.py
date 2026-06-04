# -*- coding: utf-8 -*-
"""
Тест DeepSeek Vision API с актуальными моделями.
"""

import os
import sys
import json
import base64
import struct
import zlib

from dotenv import load_dotenv
import requests

load_dotenv()

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"


def create_minimal_test_png() -> bytes:
    """Создаёт минимальный PNG 32x32 с тремя цветными полосами (RGB)."""
    width, height = 32, 32
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'
        for x in range(width):
            if x < width // 3:
                raw_data += bytes([255, 0, 0])
            elif x < 2 * width // 3:
                raw_data += bytes([0, 255, 0])
            else:
                raw_data += bytes([0, 0, 255])
    compressed = zlib.compress(raw_data)

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + chunk + crc

    png = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    png += make_chunk(b'IHDR', ihdr_data)
    png += make_chunk(b'IDAT', compressed)
    png += make_chunk(b'IEND', b'')
    return png


def get_base64_image() -> str:
    image_data = create_minimal_test_png()
    return base64.b64encode(image_data).decode('utf-8')


def test_model(model: str, use_image: bool = True) -> dict:
    """Тестирует конкретную модель с или без изображения."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    
    if use_image:
        b64 = get_base64_image()
        content = [
            {"type": "text", "text": "Describe this image in one sentence"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        ]
    else:
        content = "Hello, what model are you?"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "max_tokens": 256,
    }

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return {'status': 200, 'content': text[:200]}
        else:
            try:
                err = resp.json()
                return {'status': resp.status_code, 'error': json.dumps(err, ensure_ascii=False)[:300]}
            except:
                return {'status': resp.status_code, 'error': resp.text[:300]}
    except Exception as e:
        return {'status': -1, 'error': str(e)}


if __name__ == '__main__':
    if not API_KEY:
        print("[FAIL] DEEPSEEK_API_KEY not found in .env")
        sys.exit(1)

    print(f"API Key: ...{API_KEY[-8:]}")
    print()

    # Тестируем модели с image_url
    models_to_test = [
        ("deepseek-chat", True),
        ("deepseek-v4-flash", True),
        ("deepseek-v4-pro", True),
        ("deepseek-chat", False),  # text-only как контроль
        ("deepseek-v4-flash", False),
        ("deepseek-v4-pro", False),
    ]

    for model, use_image in models_to_test:
        label = f"{model} + {'IMAGE' if use_image else 'TEXT'}"
        print(f"[{label}] Testing...", end=" ")
        result = test_model(model, use_image)
        if result['status'] == 200:
            print(f"OK")
            print(f"  Response: {result['content'][:150]}")
        else:
            print(f"FAIL (HTTP {result['status']})")
            print(f"  Error: {result.get('error', '')[:200]}")

    print()
    print("Done.")
