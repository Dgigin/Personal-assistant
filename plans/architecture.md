# Архитектура проекта `personal_assistant`

> **Дата последнего обновления:** 2026-06-04
> **Текущая версия:** 1.0.7

---

## 📂 Структура проекта

```
f:/excel_converter/
├── app.py                  # Точка входа, Flask-фабрика, create_app()
├── wsgi.py                 # Точка входа для Waitress (production)
├── requirements.txt        # Зависимости
├── version.json            # Версия приложения + репозиторий GitHub
├── run.bat                 # Запуск с автоустановкой зависимостей + очистка stale update.bat
├── create_release.py       # Скрипт создания GitHub Release и загрузки ассетов (НЕ в git — содержит токен)
├── install_deps.bat        # Установка Python-зависимостей
├── setup_env.py            # Генератор .env с уникальным SECRET_KEY
├── installer.iss           # Inno Setup скрипт для сборки установщика
├── .env                    # SECRET_KEY, AUTH_* , DEEPSEEK_API_KEY
├── .env.example            # Шаблон .env (SECRET_KEY=__GENERATE_ME__)
├── .gitignore
│
├── config/                 # Конфигурационные JSON + SQLite
│   ├── tasks.json          # Блокнот задач
│   ├── departments.json    # Справочник подразделений (188)
│   ├── expense_articles.json # Статьи расходов (8)
│   ├── chat_history.db     # SQLite — история чатов DeepSeek
│   ├── constructor_temp_files.json  # Persist временных файлов конструктора
│   └── constructor_scenarios/ # Сценарии конструктора сводных
│
├── profiles/               # Профили маппинга Excel
│   ├── ОБИТ.json
│   └── Рест_лимит.json
│
├── src/                    # Исходный код (Flask Blueprint'ы + модели)
│   ├── config.py           # Класс Config (все настройки из .env)
│   ├── auth.py             # Сессионная аутентификация (check_session)
│   ├── types.py            # TypedDict для структур данных (PivotResult, FilterDef...)
│   ├── scheduler.py        # APScheduler — очистка uploads, сессий, архивация задач
│   ├── updater.py          # Проверка/скачивание/установка обновлений через GitHub Releases
│   ├── models/
│   │   ├── tasks.py        # Модель задач (load/save/archive)
│   │   ├── chat_db.py      # SQLite для чатов
│   │   ├── departments.py  # Подразделения
│   │   ├── expense_articles.py # Статьи
│   │   └── profiles.py     # Профили маппинга
│   ├── routes/
│   │   ├── converter_routes.py     # Конвертация Excel
│   │   ├── task_routes.py          # REST API задач
│   │   ├── constructor_routes.py   # API конструктора сводных таблиц
│   │   ├── chat_routes.py          # DeepSeek чат
│   │   └── update_routes.py        # API проверки и применения обновлений
│   ├── services/
│   │   ├── converter.py        # Логика конвертации Excel
│   │   ├── constructor.py      # Логика конструктора (pivot, фильтры, сценарии)
│   │   ├── ocr_service.py      # EasyOCR распознавание
│   │   └── chat_service.py     # Логика чата с DeepSeek
│   └── utils/
│       ├── file_utils.py       # Работа с файлами (read_file_to_df, safe_filename и т.д.)
│       ├── json_utils.py       # JSON load/save
│       └── sqlite_cache.py     # 🆕 SQLite-кэш данных листа (v1.0.8)
│
│   config/sqlite_cache/        # 🆕 Файлы SQLite-кэша конструктора (автоочистка при close_file)
│
├── templates/
│   └── index.html          # Весь фронтенд (SPA, ~4200 строк)
│
├── uploads/                # Временные файлы (автоочистка 30 мин)
├── flask_session/          # Файлы сессий Flask-Session (очистка >7 дней каждые 6ч)
├── logs/                   # Ротационные логи (10 MB × 5 файлов)
│   └── app.log
│
├── Output/                 # Собранные установщики
│   └── ExcelConverter-Setup-*.exe
│
└── plans/                  # Документация
    ├── architecture.md     # Архитектура проекта (этот файл)
    ├── security.md         # Аудит безопасности
    ├── features.md         # Функционал
    └── roadmap.md          # Дорожная карта
```

---

## 🏗️ Компоненты системы

### 1. Веб-сервер (Flask)

Приложение построено на Flask с использованием фабричной функции [`create_app()`](app.py:82):

```python
app = create_app()  # Flask-фабрика
```

- **Blueprints**: каждый модуль (конвертер, конструктор, чат, задачи, обновления) — отдельный blueprint
- **Flask-Session**: сервер-сайд сессии (файловое хранилище в `flask_session/`)
- **Waitress**: production WSGI-сервер (запуск через [`wsgi.py`](wsgi.py))
- **APScheduler**: фоновые задачи (очистка uploads, сессий, архивация задач)

### 2. Модули (src/)

| Модуль | Описание | Ключевые файлы |
|--------|----------|---------------|
| `routes/` | Контроллеры (Flask Blueprints). Принимают HTTP-запросы, вызывают сервисы | `converter_routes.py`, `constructor_routes.py`, `chat_routes.py`, `task_routes.py`, `update_routes.py` |
| `services/` | Бизнес-логика. Не зависят от Flask | `converter.py`, `constructor.py`, `ocr_service.py`, `chat_service.py` |
| `models/` | Модели данных (JSON/SQLite) | `tasks.py`, `chat_db.py`, `departments.py`, `expense_articles.py`, `profiles.py` |
| `utils/` | Утилиты | `file_utils.py`, `json_utils.py` |

### 3. Фронтенд (SPA)

Весь фронтенд — в одном HTML-файле [`templates/index.html`](templates/index.html) (~4200 строк):
- Vanilla JavaScript (без фреймворков)
- marked.js + highlight.js для рендеринга Markdown в чате
- Все стили inline (в секции `<style>`)
- Аутентификация через cookie (сессия Flask)

### 4. База данных

- **SQLite**: история чатов DeepSeek (`config/chat_history.db`)
- **SQLite (кэш)**: временное хранилище данных листа конструктора (`config/sqlite_cache/`), создаётся при `load_sheet()`, удаляется при `close_file()`
- **JSON-файлы**: задачи, справочники, профили, сценарии
- **Flask-Session**: файловое хранилище сессий

---

## 🛠️ Технологический стек

| Компонент | Технология |
|-----------|-----------|
| Веб-фреймворк | Flask (Python 3.x) |
| WSGI-сервер | Waitress (production) |
| База данных | SQLite (чат), JSON-файлы (задачи, справочники) |
| OCR | EasyOCR (локальное распознавание изображений) |
| AI-чат | DeepSeek API (streaming) |
| Фронтенд | Vanilla JS SPA, marked.js, highlight.js |
| Планировщик | APScheduler (очистка uploads 30 мин, сессий 6ч, архивация задач 5 мин) |
| Аутентификация | Flask session + куки (сервер-сайд, Flask-Session) |
| Rate limiting | Flask-Limiter (5/min на /api/login) |
| Автообновление | GitHub Releases API + `src/updater.py` (проверка раз в 6ч, скачивание ZIP) — репозиторий `Dgigin/Personal-assistant` (публичный) |
| Установщик | Inno Setup (`installer.iss`, сборка .exe) |
| Обработка данных | Pandas, openpyxl |

---

## 🔄 API-эндпоинты

### Конвертер Excel
| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/columns` | Получить колонки загруженного файла |
| POST | `/convert/stats` | Статистика по файлу |
| POST | `/convert/preview` | Предпросмотр конвертации |
| POST | `/convert/download` | Скачать результат конвертации |
| POST | `/convert/download_temp/<file_id>` | Скачать временный файл |
| POST | `/api/departments` | CRUD подразделений |
| POST | `/api/expense_articles` | CRUD статей расходов |
| POST | `/api/profiles` | CRUD профилей маппинга |

### Конструктор сводных таблиц
| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/constructor/upload` | Загрузить Excel/CSV, получить список листов |
| POST | `/api/constructor/detect_headers` | Автоопределение строки заголовков |
| POST | `/api/constructor/load` | Загрузить лист, получить данные + колонки + типы |
| POST | `/api/constructor/preview` | Применить фильтры/сортировку/пагинацию |
| POST | `/api/constructor/pivot` | Построить сводную таблицу |
| POST | `/api/constructor/download` | Сохранить результат как XLSX |
| POST | `/api/constructor/file_info` | Статус загруженного файла |
| POST | `/api/constructor/close` | Закрыть файл (удалить с сервера) |
| POST | `/api/constructor/scenario/save` | Сохранить сценарий |
| GET | `/api/constructor/scenarios` | Список сценариев |
| POST | `/api/constructor/scenario/load` | Загрузить сценарий |
| POST | `/api/constructor/scenario/delete` | Удалить сценарий |

### DeepSeek Чат
| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/chat` | Отправить сообщение в DeepSeek (streaming) |
| POST | `/api/chat/ocr` | Распознать изображение (EasyOCR) |
| POST | `/api/chat/convert_table` | Конвертировать таблицу из чата в XLSX |
| GET | `/api/conversations` | Список диалогов |
| POST | `/api/conversations` | Создать диалог |
| PUT | `/api/conversations/<id>` | Переименовать диалог |
| DELETE | `/api/conversations/<id>` | Удалить диалог |

### Обновления
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/check_update` | Проверить наличие обновления |
| GET | `/api/check_update/status` | Статус процесса обновления |
| POST | `/api/apply_update` | Запустить скачивание обновления |
| POST | `/api/apply_update/restart` | Перезапустить сервер для применения |

### Системные
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/health` | Health-check |
| GET | `/api/auth_status` | Статус аутентификации |
| POST | `/api/login` | Вход |
| POST | `/api/logout` | Выход |
| GET | `/api/tasks` | CRUD задач |
| POST | `/api/tasks` | Создать задачу |

---

## 🚀 Запуск приложения

```bash
# Production (Waitress, без баннера Flask):
python -m waitress --host=127.0.0.1 --port=5000 wsgi:application

# Development (Flask dev-server с автоперезагрузкой):
python app.py
```

---

## 📊 Статус данных

| Данные | Файл | Кол-во | Статус |
|--------|------|--------|--------|
| Задачи | `config/tasks.json` | 19+ | ✅ |
| Профили | `profiles/` | 2 | ✅ |
| Подразделения | `config/departments.json` | 188 | ✅ |
| Статьи расходов | `config/expense_articles.json` | 8 | ✅ |
| Диалоги чата | `config/chat_history.db` | 2+ | ✅ |

---

## 🔄 Процесс обновления (releases)

1. Обновить `version.json` (версия + репозиторий)
2. Обновить `create_release.py` (желательно, но файл в .gitignore)
3. Закоммитить и запушить изменения
4. Запустить `python create_release.py` — создаёт GitHub Release, загружает update.zip и установщик
5. Пользователи получают уведомление об обновлении через `/api/check_update`

**Ссылка на релизы:** https://github.com/Dgigin/Personal-assistant/releases
