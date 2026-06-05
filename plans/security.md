# Аудит безопасности проекта `personal_assistant`

> **Дата последнего обновления:** 2026-06-04
> **Текущая версия:** 1.0.7

---

## 🔐 Сводка аудита безопасности

Проведён аудит. **16 проблем:** 2 CRITICAL, 5 HIGH, 5 MEDIUM, 4 LOW.

| # | Уровень | Проблема | Статус |
|---|---------|----------|--------|
| C1 | 🔴 CRITICAL | Hardcoded SECRET_KEY (fallback `'supersecretkey'`) | ✅ Убран fallback, добавлена проверка при старте |
| C2 | 🔴 CRITICAL | DEEPSEEK_API_KEY в коде (ранее читался из `.env` при каждом запросе) | ✅ Загружается один раз в Config.DEEPSEEK_API_KEY |
| H1 | 🟠 HIGH | Отсутствие Content-Security-Policy | ✅ Добавлен CSP (script-src, style-src, connect-src) |
| H2 | 🟠 HIGH | MIME-sniffing (X-Content-Type-Options) | ✅ Добавлен `nosniff` |
| H3 | 🟠 HIGH | Clickjacking (X-Frame-Options) | ✅ Добавлен `DENY` |
| H4 | 🟠 HIGH | Referrer leakage | ✅ `Referrer-Policy: no-referrer` |
| H5 | 🟠 HIGH | DeepSeek чат включён по умолчанию (утечка данных) | ✅ Выключен по умолчанию, toggle + предупреждение безопасности |
| M1 | 🟡 MEDIUM | Debug-режим Flask | ✅ Отключён (`debug=False` в app.py, production через wsgi.py) |
| M2 | 🟡 MEDIUM | Отсутствие сессионной аутентификации | ✅ Добавлена (login/logout, `check_session()`) |
| M3 | 🟡 MEDIUM | Разлогин через keepalive не работал (10 мин) | ✅ Исправлен — `/api/auth_status` не обновляет `last_activity` |
| M4 | 🟡 MEDIUM | API-ключ в репозитории (git) | ✅ `.gitignore` содержит `.env` |
| M5 | 🟡 MEDIUM | Нет ротации логов | ✅ RotatingFileHandler (10 MB × 5) |
| M6 | 🟡 MEDIUM | Нет CSRF-защиты (mitigated через SameSite+Lax + Content-Type check) | ⚠️ Частично прикрыто, предлагается Origin/Referer middleware |
| M7 | 🟡 MEDIUM | `unsafe-inline` в CSP (весь JS/CSS встроен в HTML) | ⚠️ Вынести в статические файлы — большая реорганизация |
| L1 | 🟢 LOW | SECRET_KEY может быть пустым — теперь обязателен | ✅ Фатальная ошибка при старте, если не задан. Уникальный ключ генерируется `setup_env.py` |
| L2 | 🟢 LOW | clean_old_uploads не вызывался при старте через wsgi.py | ✅ Вызов перенесён внутрь `create_app()` |
| L3 | 🟢 LOW | SESSION_COOKIE_SECURE не настраивался | ✅ Настраивается через .env |
| L4 | 🟢 LOW | Нет rate limiting на /api/login | ✅ Flask-Limiter, 5 запросов в минуту |

---

## 📋 Детальный аудит архитектуры

Аудит проведён 02.06.2026. Выявлено **15 проблем** в категориях Security, Architecture, Code Quality, Performance, Reliability.

### 1. 🔴 Security — SECRET KEY может быть пустым

**Было:** [`src/config.py:33`](src/config.py:33) — fallback `''` (пустая строка).
**Стало:** Если SECRET_KEY не задан в `.env` — `sys.exit(1)` с сообщением в логе.
**Статус:** ✅ Исправлено

### 2. 🔴 Architecture — In-memory `_temp_files`

**Было:** Словарь в памяти модуля constructor_routes — теряется при рестарте.
**Стало:**
- Добавлен JSON-файл `config/constructor_temp_files.json`
- Функции `_load_temp_files()` / `_save_temp_files()` — persist при старте и после каждого изменения
- Функция `_clean_orphan_uploads()` — удаляет файлы без ссылок в `_temp_files`
**Статус:** ✅ Исправлено

### 3. 🟡 Security — Нет rate limiting на /api/login

**Было:** Эндпоинт логина без защиты от brute-force.
**Стало:** `flask-limiter` — `@limiter.limit("5/minute")` на `/api/login`.
**Статус:** ✅ Исправлено

### 4. 🟡 Security — SESSION_COOKIE_SECURE=False

**Было:** Жёстко `False` в app.py.
**Стало:** Читается из `.env`: `SESSION_COOKIE_SECURE=True/False`.
**Статус:** ✅ Исправлено

### 5. 🟡 Code Quality — Дублирование фильтрации

**Было:** `apply_filters()` и `build_pivot_table()` — каждая со своей логикой.
**Стало:** Единая `_apply_filters_to_df(df, filters)` — 7 типов фильтров.
**Статус:** ✅ Исправлено

### 6. 🟡 Performance — Нет кэширования DataFrame

**Было:** Каждый вызов читал Excel с диска.
**Стало:** `cached_df: Optional[pd.DataFrame]` в `_temp_files`.
**Статус:** ✅ Исправлено

### 7. 🟡 Reliability — Нет лимита истории DeepSeek

**Было:** Вся история отправлялась в API — риск превышения контекстного окна.
**Стало:** `MAX_HISTORY_MESSAGES = 50` в chat_routes.py.
**Статус:** ✅ Исправлено

### 8. 🟠 Code Quality — Нет TypedDict

**Было:** Все функции возвращали `Dict[str, Any]`.
**Стало:** [`src/types.py`](src/types.py) — `FilterDef`, `PivotResult`, `ScenarioParams`, `ScenarioData`, `LoadSheetResult`, `ApplyFiltersResult`.
**Статус:** ✅ Исправлено

### 9. 🟠 Code Quality — `except: pass`

**Было:** 3 места с `except: pass` (file_utils.py, profiles.py, constructor.py).
**Стало:** `except Exception as e: logger.warning('... %s', e)`.
**Статус:** ✅ Исправлено

### 10. 🟠 Architecture — Планировщики в app.py

**Было:** 3 функции-планировщика внутри `app.py` + обработчики сигналов.
**Стало:** [`src/scheduler.py`](src/scheduler.py) — модуль с 3 планировщиками + `atexit`.
**Статус:** ✅ Исправлено

### 11. 🟢 Code Quality — Магические строки

**Было:** `'__agg__'`, `'__год__'`, `'__месяц__'` хардкожены.
**Стало:** Константы `AGG_COLUMN_NAME`, `DATE_PREFIXES` на уровне модуля.
**Статус:** ✅ Исправлено

### 12. 🟢 Code Quality — Импорт `re` внутри функции

**Было:** `import re as re_mod` внутри `_infer_column_types()`.
**Стало:** `import re` на уровне модуля constructor.py.
**Статус:** ✅ Исправлено

### 13. 🟢 Reliability — Graceful shutdown

**Было:** `sys.exit(0)` без ожидания планировщиков.
**Стало:** `atexit.register(stop_schedulers)`.
**Статус:** ✅ Исправлено

### 14. 🟢 Reliability — clean_old_uploads не вызывался через wsgi.py

**Было:** Вызов только в `if __name__ == '__main__'`.
**Стало:** Вызов внутри `create_app()`.
**Статус:** ✅ Исправлено

### 15. 🟢 Generator — Завершение после ошибки DeepSeek

**Было:** После `yield` ошибки генератор продолжал работу.
**Стало:** `return` после `yield error`.
**Статус:** ✅ Исправлено

---

## 🛡️ Рекомендации по дальнейшему улучшению

### CSRF-защита (Фаза 4.1)

**Что уже есть:**
- `SESSION_COOKIE_SAMESITE='Lax'`
- Проверка `Content-Type` в chat_routes.py

**Что рекомендуется добавить:**
```python
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect()
csrf.init_app(app)
```

Для API-эндпоинтов (POST/PUT/DELETE): добавить `_csrf_token` в тело запроса или заголовок `X-CSRFToken`.

### Санация имён файлов (Фаза 4.2)

**Что уже есть:**
- `secure_filename(file.filename)` в [`constructor_routes.py:186`](src/routes/constructor_routes.py:186)

**Что проверить:**
- Все ли места загрузки используют `secure_filename`?
- [`converter_routes.py`](src/routes/converter_routes.py) — проверить на path traversal

---

## 🔧 Меры безопасности, реализованные в разных версиях

### v1.0.3
- Генератор `.env` с уникальным SECRET_KEY (`setup_env.py`)
- Проверка наличия SECRET_KEY при старте (фатальная ошибка, если отсутствует)

### v1.0.4
- CSP-заголовки (Content-Security-Policy)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: no-referrer
- Rate limiting на /api/login (5/min)
- Сессионная аутентификация

### v1.0.5
- Подавление логов Werkzeug (только ERROR)
- Очистка stale update-файлов при старте

### v1.0.6
- Полная переработка механизма обновления (устранение `del "%~f0"`)
- Перенос логики обновления в `apply_update.py`

### v1.0.7
- Поддержка CSV-файлов (проверка расширения + безопасное чтение)
- Централизованная `read_file_to_df()` с автоопределением кодировки
