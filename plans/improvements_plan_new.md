# Проект `excel_converter` — Единый план и документация

> **Дата последнего обновления:** 2026-06-04 (v11)
> **Единый файл,** заменивший: `architecture_analysis.md`, `audit_report.md`, `improvements_plan.md`, `security_audit_report.md`, `vision_integration_plan.md`, `fix_implementation_plan.md`, `new_features_plan.md`

---

## 📂 Архитектура проекта

```
f:/excel_converter/
├── app.py                  # Точка входа, Flask-фабрика, create_app()
├── wsgi.py                 # Точка входа для Waitress (production)
├── requirements.txt        # Зависимости
├── version.json            # Версия приложения + репозиторий GitHub
├── run.bat                 # Запуск с автоустановкой зависимостей + очистка stale update.bat (v1.0.5)
├── create_release.py       # Скрипт создания GitHub Release и загрузки ассетов
├── install_deps.bat        # Установка Python-зависимостей
├── setup_env.py            # Генератор .env с уникальным SECRET_KEY (v1.0.3)
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
│   ├── updater.py          # Проверка/скачивание/установка обновлений через GitHub Releases (v1.0.4: zipfile вместо tar/PowerShell; v1.0.6: убран del "%~f0")
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
│       ├── file_utils.py   # Работа с файлами
│       └── json_utils.py   # JSON load/save
│
├── templates/
│   └── index.html          # Весь фронтенд (SPA, ~3900 строк)
│
├── uploads/                # Временные файлы (автоочистка 30 мин)
├── flask_session/          # Файлы сессий Flask-Session (очистка >7 дней каждые 6ч)
├── logs/                   # Ротационные логи (10 MB × 5 файлов)
│   └── app.log
│
└── plans/                  # Документация
    └── improvements_plan_new.md  # ⬅ ЕДИНСТВЕННЫЙ файл
```

### Технологический стек

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

---

## 🔐 Аудит безопасности — статус

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

## 🖼️ Интеграция EasyOCR (распознавание изображений)

**Статус:** ✅ Реализовано и протестировано

### Что сделано

1. **Библиотека:** EasyOCR (русский + английский языки) — установлена, добавлена в [`requirements.txt`](requirements.txt)
2. **Сервис:** [`src/services/ocr_service.py`](src/services/ocr_service.py) — класс `OCRService`
3. **API:** POST `/api/chat/ocr` — принимает изображение (base64), возвращает распознанный текст
4. **UI:** В чат добавлена загрузка изображений, скачивание результата как `.xlsx`

---

## ✅ Итоговый список улучшений (25 пунктов)

Все пункты выполнены.

### 1–23. Предыдущие улучшения
*(см. ниже раздел "Ранее реализованные улучшения")*

---

## 🚀 НОВЫЙ ПЛАН: Улучшение инструментария

### 🔄 Текущая структура вкладок

| # | Вкладка | Описание |
|---|---------|----------|
| 1 | Конвертация | Загрузка Excel + профиль → статистика/скачивание |
| 2 | Профили | Создание/редактирование профилей маппинга |
| 3 | Справочники | Подразделения (188) + Статьи расходов (8) |
| 4 | DeepSeek | Чат с DeepSeek AI + OCR |

### 🎯 Целевая структура вкладок (ИТОГ)

| # | Вкладка | Описание |
|---|---------|----------|
| 1 | **🔄 Конвертер** | Переименовано из "Конвертация" |
| 2 | **📁 Профили** | Без изменений |
| 3 | **🏢 Справочники** | Без изменений |
| 4 | **🔧 Конструктор** | 🆕 Low-code конструктор сводных таблиц |
| 5 | **💬 DeepSeek** | Перемещён с 4-й на 5-ю позицию |

---

## 🏗️ Концепция: Конструктор сводных таблиц (Low-code)

### 📋 Назначение

Позволяет загрузить **любой Excel-файл** и визуально, без программирования:
1. Просмотреть содержимое
2. Выбрать нужные колонки
3. Применить фильтры
4. Сгруппировать данные
5. Построить сводную таблицу (Pivot)
6. Выгрузить результат в XLSX / CSV

### 🔧 API-эндпоинты (реализовано — 12 шт.)

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/constructor/upload` | Загрузить Excel, получить список листов + UUID файла |
| POST | `/api/constructor/detect_headers` | Автоопределение строки заголовков + предпросмотр первых 10 строк |
| POST | `/api/constructor/load` | Загрузить лист, получить данные (100 строк) + колонки + типы |
| POST | `/api/constructor/preview` | Применить фильтры/сортировку/пагинацию, предпросмотр |
| POST | `/api/constructor/pivot` | Построить сводную таблицу (rows, cols, values, agg_functions) |
| POST | `/api/constructor/download` | Сохранить pivot как XLSX, вернуть file_id для скачивания |
| POST | `/api/constructor/file_info` | Проверить статус загруженного файла |
| POST | `/api/constructor/close` | Закрыть файл (удалить с сервера) |
| POST | `/api/constructor/scenario/save` | Сохранить сценарий |
| GET | `/api/constructor/scenarios` | Список сценариев |
| POST | `/api/constructor/scenario/load` | Загрузить сценарий |
| POST | `/api/constructor/scenario/delete` | Удалить сценарий |

### 🎨 UI-компоненты (фронтенд)

1. **Загрузка файла** — выбор файла, список листов
2. **Панель данных** — табличный просмотр с сортировкой по колонкам
3. **Панель трансформации:**
   - Выбор колонок для отображения
   - Фильтры (текстовые, числовые, дата)
4. **Панель сводной таблицы:**
   - Выбор строк (rows)
   - Выбор колонок (cols)
   - Выбор значений (values)
   - Функция агрегации (sum, avg, count, min, max, none)
   - Формат вывода (плоский / иерархический)
5. **Выгрузка** — скачивание XLSX

### 📊 Пример использования

```
1. Загрузить "Отчёт_продаж.xlsx"
2. Выбрать лист "Продажи"
3. Отфильтровать: "Дата > 01.01.2024"
4. Сводная: строки = "Регион", колонки = "Квартал", значения = "Сумма" (sum)
5. Скачать XLSX
```

---

## 🚀 Приоритетные улучшения (дорожная карта)

### Фаза 1 — Базовая (завершено)
- [x] ✅ Переименована вкладка "Конвертация" → "Конвертер"
- [x] ✅ Добавлена 4-я вкладка "🔧 Конструктор" (между Справочники и DeepSeek)
- [x] ✅ DeepSeek стал 5-й вкладкой
- [x] ✅ Создан сервис `constructor.py` — 6 функций (загрузка, фильтры, pivot, экспорт)
- [x] ✅ Создан blueprint `constructor_routes.py` — 7 эндпоинтов
- [x] ✅ Фронтенд: загрузка файла → выбор листа → фильтры → pivot → скачивание XLSX
- [x] ✅ **Исправление:** кнопка "Сбросить" теперь очищает selection в мультиселектах сводной (строки/значения/колонки) и сбрасывает агрегацию на "sum"
- [x] ✅ **Исправление:** добавлены CSS-спиннеры и блокировка кнопок на все async-операции (загрузка файла, загрузка листа, фильтры, построение сводной, скачивание) — индикация процесса через `setConstructorLoading()`

### Фаза 2 — Спринт: Конструктор v2 (даты, агрегация, сценарии, мульти-агрегация) — ✅ ЗАВЕРШЕНО
- [x] **Декомпозиция datetime** — авто-определение date-колонок, суб-опции (год/квартал/месяц/день) в мультиселектах, виртуальные колонки в `build_pivot_table()`
- [x] **Агрегация "Без изменений"** — опция `value="none"` в agg function, `build_pivot_table()` возвращает raw data без pivot
- [x] **Высота мультиселектов** — `height:80px` → `height:200px` для строк/значений/колонок
- [x] **Сохранение сценариев** — JSON-файлы в `config/constructor_scenarios/`, API save/load/list/delete, UI кнопки "💾 Сохранить" / "📂 Загрузить"
- [x] **Улучшение UI "Отображаемые колонки"** — поиск (🔍), кнопки "✅ Все" / "❌ Ни одной", `max-height: 150px` → `300px`
- [x] **Исправление детекции дат** — числовые колонки больше не помечаются как `date` (приоритет number → date → text, regex-паттерн даты)
- [x] **Мульти-агрегация** — поддержка выбора нескольких функций агрегации одновременно, два формата вывода (плоский/иерархический), `<select multiple>` + переключатель формата

### Фаза 2.5 — Аудит архитектуры и code quality (✅ ЗАВЕРШЕНО)
- [x] TypedDict для структур данных ([`src/types.py`](src/types.py))
- [x] Константы для магических строк (`AGG_COLUMN_NAME`, `DATE_PREFIXES`) в constructor.py
- [x] Импорт `re` на уровень модуля (constructor.py)
- [x] Замена `except: pass` на `logger.warning` (file_utils.py, profiles.py, constructor.py)
- [x] Завершение генератора после ошибки DeepSeek (chat_service.py)
- [x] Общая функция фильтрации `_apply_filters_to_df()` — 7 типов (constructor.py)
- [x] Кэширование DataFrame (cached_df в _temp_files)
- [x] Persist `_temp_files` в JSON (constructor_routes.py)
- [x] Усечение истории DeepSeek (MAX_HISTORY_MESSAGES=50)
- [x] Вынос планировщиков в `src/scheduler.py` + session cleanup (6ч, >7 дней)
- [x] Graceful shutdown через `atexit`
- [x] clean_old_uploads при старте через `create_app()`
- [x] Rate limiting на /api/login (Flask-Limiter, 5/min)
- [x] SESSION_COOKIE_SECURE настраиваемый через .env
- [x] **Баг-фикс:** кнопка "Сбросить" теперь полностью очищает `<option>` в селектах pivot (не только `selected`)

### Фаза 2.6 — Оптимизация загрузки данных в Конструкторе (📋 план)

**Текущая проблема:** При выборе листа и нажатии "Загрузить" endpoint `/api/constructor/load` делает две тяжёлые операции — читает Excel для кэширования и ещё раз для `load_sheet_data()`. Фронтенд сразу отображает 100 строк в таблице, хотя пользователь ещё не выбрал колонки и не настроил фильтры.

**Решение:** Разделить загрузку на два этапа:
1. `/api/constructor/load` — только метаданные (columns, dtypes, date_columns, total_rows), **без data**
2. Таблицу показывать только когда пользователь явно запросит данные (фильтры или сводная)

**Что меняется:**
- **Бэкенд** [`src/routes/constructor_routes.py:208`](src/routes/constructor_routes.py:208): `load_sheet()` — убрать вызов `load_sheet_data()`, оставить только кэширование + метаданные
- **Фронтенд** [`templates/index.html`](templates/index.html): убрать `renderConstructorDataTable` из обработчика `constructorLoadSheetBtn`, добавить сообщение "Загружено N строк. Используйте фильтры или стройте сводную."

**Эффект:**

| Метрика | До | После |
|---------|----|-------|
| Чтений Excel при загрузке листа | 2 | 1 |
| Передача данных JSON | columns + 100 строк (десятки КБ) | только columns (сотни байт) |
| Рендеринг таблицы в браузере | Всегда | Только по запросу |
| Нагрузка на сервер | Высокая (read + to_dict + sanitize + jsonify) | Минимальная |
| Время загрузки листа | Медленно (зависит от размера файла) | Быстро (только мета) |

**Риски:**
1. Потеря "предпросмотра" — пользователь не видит данные сразу после выбора листа. Компенсируется сообщением о количестве строк.
2. Обратная совместимость — если `load_sheet_data()` используется где-то ещё, её нельзя удалять.

### Фаза 3 — Расширение функционала
- [ ] Графики и визуализация на основе сводных таблиц
- [ ] История загрузок файлов
- [ ] Экспорт сводных таблиц в PDF

### Фаза 4 — Интеграции
- [ ] Подключение к 1С / SAP / ERP через REST API
- [ ] Планировщик регулярных выгрузок
- [ ] Telegram-бот для получения отчётов

---

## 📐 Спецификация: Конструктор v2 (4 задачи)

### 1. Декомпозиция datetime

**Бэкенд** — [`src/services/constructor.py`](src/services/constructor.py):
- В `load_sheet_data()`: если `dtypes[col] == 'date'`, добавить в ответ `date_columns: ["Дата", ...]`
- Новый метод `decompose_date_column(series: pd.Series) -> dict`: разбивает на `{__год__, __квартал__, __месяц__, __день__}`. Месяц — название (Январь, Февраль...).
- В `build_pivot_table()`: перед группировкой проверить `rows` и `cols` на префиксы `__год__`, `__квартал__`, `__месяц__`, `__день__`. Если найдены — вызвать `decompose_date_column()` для родительской колонки, добавить виртуальные колонки в df.
- Формат суб-колонки: `__год__Дата` (префикс + имя родительской колонки)

**Фронтенд** — [`templates/index.html`](templates/index.html):
- `renderConstructorPivotSelects(columns, dateColumns)`: для date-колонок добавить 4 опции с иконкой 📅 и отступом:
  ```
  Дата
    📅 Дата ▸ год
    📅 Дата ▸ квартал
    📅 Дата ▸ месяц
    📅 Дата ▸ день
  ```
- Перед отправкой `POST /api/constructor/pivot`: преобразовать `Дата ▸ год` → `__год__Дата`, `Дата ▸ месяц` → `__месяц__Дата` и т.д.

### 2. Агрегация "Без изменений"

**Бэкенд** — [`src/services/constructor.py`](src/services/constructor.py):
- В `build_pivot_table()`: если `agg_function == 'none'`:
  - Не вызывать `pd.pivot_table()` и не делать `.groupby()`
  - Прочитать данные, применить фильтры, выбрать колонки из `rows + values + cols`
  - Вернуть как плоскую таблицу (каждая строка уникальна)
- Если `agg_function == 'none'` и `cols` не пуст — всё равно вернуть плоские данные, просто с выбранными колонками

**Фронтенд** — [`templates/index.html`](templates/index.html):
- В `<select id="constructorAggFunction">` добавить:
  ```html
  <option value="none">🔹 Без изменений</option>
  ```

### 3. Высота мультиселектов

- [`templates/index.html`](templates/index.html:366): `height:80px` → `height:200px; min-height:150px` для всех трёх `<select multiple>` (строки, значения, колонки)

### 4. Сохранение сценариев

**Хранение:** JSON-файлы в `config/constructor_scenarios/{name}.json`

**Структура сценария:**
```json
{
  "name": "Продажи по регионам",
  "created_at": "2026-06-02T14:00:00",
  "updated_at": "2026-06-02T14:00:00",
  "params": {
    "columns": ["Регион", "Товар", "Сумма"],
    "filters": [{"column": "Регион", "type": "equals", "value": "Москва"}],
    "pivot_rows": ["Регион"],
    "pivot_values": ["Сумма"],
    "pivot_cols": [],
    "agg_function": "sum"
  }
}
```

**Новые эндпоинты** — [`src/routes/constructor_routes.py`](src/routes/constructor_routes.py):

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/constructor/scenario/save` | Создать/обновить сценарий |
| GET | `/api/constructor/scenarios` | Список всех сценариев |
| POST | `/api/constructor/scenario/load` | Загрузить сценарий по имени |
| POST | `/api/constructor/scenario/delete` | Удалить сценарий |

**Новый сервис** — в [`src/services/constructor.py`](src/services/constructor.py):
- `save_scenario(name, params)`: сохраняет JSON в `config/constructor_scenarios/`
- `list_scenarios()`: читает все JSON из директории
- `load_scenario(name)`: загружает конкретный JSON
- `delete_scenario(name)`: удаляет JSON-файл

**Фронтенд** — [`templates/index.html`](templates/index.html):
- Кнопка "💾 Сохранить" рядом с "Сбросить" — открывает модальное окно ввода имени
- Выпадающий список "📂 Загрузить" — при выборе сценария заполняет все параметры (колонки, фильтры, pivot)
- Крестик "✖" рядом с именем сценария в списке — удаление с подтверждением

### 5. Мульти-агрегация (несколько функций одновременно)

**Бэкенд** — [`src/services/constructor.py`](src/services/constructor.py):
- Параметр `agg_function: str` заменён на `agg_functions: List[str]` — теперь принимает список функций
- Функция `build_pivot_table()` получила новый параметр `output_format: str = 'flat'`
- **Плоский (широкий) формат:** для каждой функции агрегации вычисляется сводная, колонки переименовываются с суффиксом `({agg_label})`, например: `Сумма (sum)`, `Сумма (mean)`. Результаты объединяются через `pd.merge()` по row-колонкам.
- **Иерархический (вертикальный) формат:** каждая агрегация — отдельная строка с колонкой `__agg__` (показатель). Строки группируются по row-колонкам, сортируются. Колонки: `[row_cols, "__agg__", value_cols...]`.
- Поддержка `cols` (колонки сводной) в обоих форматах. В иерархическом формате колонки сводной присутствуют как отдельные колонки.
- Режим `'none'` в списке — возвращает сырые данные.

**Маршрут** — [`src/routes/constructor_routes.py`](src/routes/constructor_routes.py):
- Параметр `agg_function` заменён на `agg_functions: List[str]`
- Добавлен параметр `output_format: 'flat'|'hierarchical'`

**Фронтенд** — [`templates/index.html`](templates/index.html):
- `<select id="constructorAggFunction">` изменён на `multiple` с `height:200px` (вместо единственного выбора)
- Добавлен переключатель формата вывода — два радио-инпута: "📐 Плоский" / "📋 Иерархический" с визуальным выделением (зелёная рамка)
- Функция `renderConstructorDataTable()` обновлена: для иерархического формата группирует строки по `row_columns`, использует `rowspan` для объединения ячеек, стилизует колонку `__agg__` зелёным фоном
- Функция `updateOutputFormatStyle()` — подсвечивает выбранный формат
- Сообщение об успехе показывает все выбранные агрегации и формат

**Пример вывода (иерархический):**
```
| Город | __agg__       | Продажи | Кол-во |
|-------|---------------|---------|--------|
| Москва| Сумма (sum)   | 100     | 5      |
|       | Среднее (mean)| 50      | 2.5    |
| СПб   | Сумма (sum)   | 200     | 10     |
|       | Среднее (mean)| 100     | 5      |
```

---

## 📊 Аудит архитектуры — результаты и исправления

Аудит проведён 02.06.2026. Выявлено **14 проблем** в категориях Security, Architecture, Code Quality, Performance, Reliability.

### 1. 🔴 Security — SECRET_KEY может быть пустым
**Было:** [`src/config.py:33`](src/config.py:33) — fallback `''` (пустая строка).
**Стало:** Если SECRET_KEY не задан в `.env` — `sys.exit(1)` с сообщением в логе.
**Статус:** ✅ Исправлено (пользователь подтвердил, что добавил в .env)

### 2. 🔴 Architecture — In-memory `_temp_files`
**Было:** Словарь в памяти модуля constructor_routes — теряется при рестарте.
**Стало:** 
- Добавлен JSON-файл `config/constructor_temp_files.json`
- Функции `_load_temp_files()` / `_save_temp_files()` — persist при старте и после каждого изменения
- Функция `_clean_orphan_uploads()` — удаляет файлы без ссылок в `_temp_files`
- `import pandas as pd` добавлен в constructor_routes.py для кэширования DataFrame
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
**Было:** `apply_filters()` и `build_pivot_table()` — каждая со своей логикой. `build_pivot_table` поддерживала только `equals`/`contains`.
**Стало:** Единая `_apply_filters_to_df(df, filters)` — 7 типов: `equals`, `contains`, `not_equals`, `greater_than`, `less_than`, `is_empty`, `is_not_empty`. Используется в обоих функциях.
**Статус:** ✅ Исправлено

### 6. 🟡 Performance — Нет кэширования DataFrame
**Было:** Каждый вызов `load_sheet_data()`, `apply_filters()`, `build_pivot_table()` читал Excel с диска.
**Стало:** `cached_df: Optional[pd.DataFrame]` в `_temp_files`. Endpoints передают `cached_df` в функции. При `close_file()` кэш инвалидируется.
**Статус:** ✅ Исправлено

### 7. 🟡 Reliability — Нет лимита истории DeepSeek
**Было:** Вся история отправлялась в API — риск превышения контекстного окна.
**Стало:** `MAX_HISTORY_MESSAGES = 50` в chat_routes.py. Системное сообщение всегда первое.
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
**Стало:** [`src/scheduler.py`](src/scheduler.py) — модуль с 3 планировщиками (uploads 30 мин, задачи 5 мин, сессии 6ч) + `atexit` для graceful shutdown.
**Статус:** ✅ Исправлено

### 11. 🟢 Code Quality — Магические строки
**Было:** `'__agg__'`, `'__год__'`, `'__месяц__'` хардкожены.
**Стало:** `AGG_COLUMN_NAME = '__agg__'`, `DATE_PREFIXES = {'__год__', '__квартал__', '__месяц__', '__день__'}` на уровне модуля.
**Статус:** ✅ Исправлено

### 12. 🟢 Code Quality — Импорт `re` внутри функции
**Было:** `import re as re_mod` внутри `_infer_column_types()`.
**Стало:** `import re` на уровне модуля constructor.py.
**Статус:** ✅ Исправлено

### 13. 🟢 Reliability — Graceful shutdown
**Было:** `sys.exit(0)` без ожидания планировщиков.
**Стало:** `atexit.register(stop_schedulers)` — ждёт завершения всех задач.
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

## 🐛 Баг-фикс: «Сбросить» в конструкторе не очищает параметры сводной таблицы

**Дата:** 02.06.2026
**Файл:** [`templates/index.html:2642-2648`](templates/index.html:2642)
**Приоритет:** 🔴 Critical (UX)

### Проблема
При нажатии на кнопку "Сбросить" код только сбрасывал `selected` у `<option>` элементов в селектах `constructorPivotRows`, `constructorPivotValues`, `constructorPivotCols`, но не удалял сами `<option>` из DOM:

```javascript
// БЫЛО — только сбрасывает выделение
Array.from(sel.options).forEach(o => o.selected = false);
```

После сброса и загрузки нового файла, upload handler сразу показывал `constructorStep2` (`display: block`), а селекты всё ещё содержали `<option>` из предыдущего файла. Функция `renderConstructorPivotSelects()` вызывается только в load-sheet handler (по клику "📥 Загрузить"), поэтому старые опции оставались видимыми.

### Исправление
```javascript
// СТАЛО — полностью очищает <select>
sel.innerHTML = '';
```

При следующей загрузке листа `renderConstructorPivotSelects()` заполнит селекты через `innerHTML = renderOptions(columns)` с новыми колонками.

---

## 🔧 Файлы, изменённые в рамках реализации

| Файл | Изменения |
|------|-----------|
| [`templates/index.html`](templates/index.html) | + кнопка 5-й вкладки "🔧 Конструктор" · + HTML-панель (шаг 1: загрузка, шаг 2: лист/фильтры/pivot/скачивание) · + ~200 строк JS логики · **v2:** высота селектов 200px, агрегация "Без изменений", дата-подопции (📅 ▸ год/квартал/месяц/день), UI сценариев (💾 Save / 📂 Load), поиск колонок + кнопки "✅ Все"/"❌ Ни одной" · **v3:** `title`-атрибуты для всех интерактивных элементов (кроме Блокнота задач) · **v4:** панель сценариев перенесена наверх (перед загрузкой файла) + `scrollIntoView()` · **v5:** баг-фикс — кнопка "Сбросить" теперь очищает `innerHTML` селектов, а не только `selected` · **v6:** + чекбокс "📊 Итого" с оранжевым стилем рядом с кнопкой "Построить сводную", передача `show_totals` в теле запроса · **v7:** UI редизайн — чекбокс "📊 Итого" заменён на iOS-style toggle switch (`initTotalsToggle()`), радио-инпуты "Плоский/Иерархический" заменены на segmented buttons (`updateOutputFormatStyle2()`) · **v8:** баг-фикс — `e.preventDefault()` в `initTotalsToggle()` (двойное переключение из-за label) · **v9:** новый HTML-модал `constructorHeaderDialog` для выбора строки заголовков + чекбокс транспонирования · JS: `constructorSheetHeaderConfig`, `_pendingHeaderData`, `showHeaderDialog()`, `closeHeaderDialog()`, `confirmHeaderDialog()`, `loadConstructorSheetData()` · Обновлён `constructorLoadSheetBtn` — автоопределение через `/api/constructor/detect_headers` · + `header_row` в preview, pivot, scenario save/apply |
| [`app.py`](app.py) | + `from src.routes.constructor_routes import constructor_bp` · + `app.register_blueprint(constructor_bp)` · **v2:** Flask-Session (сервер-сайд сессии, файловое хранилище) + очистка сессий при старте · **v3:** Вынос планировщиков в scheduler.py, Flask-Limiter (5/min на /api/login), SESSION_COOKIE_SECURE из .env, clean_old_uploads в create_app() |
| [`src/routes/constructor_routes.py`](src/routes/constructor_routes.py) | 🆕 7 эндпоинтов · **v2:** +4 эндпоинта сценариев + импорт `_ensure_scenarios_dir` · **v3:** Persist `_temp_files` в JSON, кэширование DataFrame (cached_df), `_clean_orphan_uploads()`, импорт pandas · **v4:** + параметр `show_totals` в `/api/constructor/pivot`, передача в `build_pivot_table(show_totals=show_totals)` · **v5:** + новый эндпоинт `/api/constructor/detect_headers` · + параметры `header_row` и `transpose` в `/api/constructor/load` · + параметр `header_row` в `/api/constructor/preview` и `/api/constructor/pivot` |
| [`src/services/constructor.py`](src/services/constructor.py) | 🆕 6 функций бизнес-логики · **v2:** рефакторинг: `decompose_date_column()`, `_apply_date_decomposition()`, `resolve_cols()`, `agg_function='none'`, 4 функции сценариев · **v3:** иерархический формат + `fillna(0)` · **v4:** единая `_apply_filters_to_df()`, константы (AGG_COLUMN_NAME, DATE_PREFIXES), импорт `re` на уровень модуля, TypedDict-импорты · **v5:** баг-фикс декомпозиции дат (`dayfirst=True`, NaT → `''` для года/квартала/дня) + параметр `show_totals` в `build_pivot_table()` с `margins=show_totals, margins_name='Итого'` · **v6:** новая функция `_parse_dates_flexible()` — универсальный парсер дат (ISO + русский формат), замена прямых вызовов `pd.to_datetime()` в `_infer_column_types()` и `decompose_date_column()`, импорт `warnings` · **v7:** баг-фикс — сортировка "Итого" строк в иерархическом формате (перемещение в конец после сортировки, т.к. "И" < "М" для "Май") · **v8:** баг-фикс — добавлен `format='mixed'` в оба вызова `pd.to_datetime()` внутри `_parse_dates_flexible()` для совместимости с pandas 3.x (без формата не парсятся смешанные форматы с/без микросекунд) · **v9:** + `_detect_header_row()` — автоопределение строки заголовков · + `transpose` в `load_sheet_data()` · + `_infer_column_types_from_df()` — инлайн-определение типов для транспонированных данных · + `header_row` в `apply_filters()` и `build_pivot_table()` |
| [`src/routes/chat_routes.py`](src/routes/chat_routes.py) | MAX_HISTORY_MESSAGES=50, усечение истории перед отправкой в DeepSeek API |
| [`src/services/chat_service.py`](src/services/chat_service.py) | `return` после `yield` ошибки в генераторе |
| [`src/utils/file_utils.py`](src/utils/file_utils.py) | `except: pass` → `logger.warning` |
| [`src/models/profiles.py`](src/models/profiles.py) | `except: pass` → `logger.warning` |
| [`src/types.py`](src/types.py) | 🆕 TypedDict: FilterDef, PivotResult, ScenarioParams, ScenarioData, LoadSheetResult, ApplyFiltersResult |
| [`src/scheduler.py`](src/scheduler.py) | 🆕 Модуль с 3 планировщиками (uploads/30min, tasks/5min, sessions/6h) + graceful shutdown через atexit |
| [`src/config.py`](src/config.py) | + `SESSION_COOKIE_SECURE` читается из .env |
| [`requirements.txt`](requirements.txt) | + `flask-limiter>=3.7` |

---

## 📊 Статус данных (все целы)

| Данные | Файл | Кол-во | Статус |
|--------|------|--------|--------|
| Задачи | [`config/tasks.json`](config/tasks.json) | 19+ | ✅ |
| Профили | [`profiles/`](profiles/) | 2 | ✅ |
| Подразделения | [`config/departments.json`](config/departments.json) | 188 | ✅ |
| Статьи расходов | [`config/expense_articles.json`](config/expense_articles.json) | 8 | ✅ |
| Диалоги чата | [`config/chat_history.db`](config/chat_history.db) | 2+ | ✅ |

---

## 🚀 Запуск приложения

```bash
# Production (Waitress, без баннера Flask):
python -m waitress --host=127.0.0.1 --port=5000 wsgi:application

# Development (Flask dev-server с автоперезагрузкой):
python app.py
```

---

## 🔧 Ранее реализованные улучшения

### 1. Удалить мёртвый файл `config/articles.json`
- Дубликат `expense_articles.json`, нигде не использовался
- **Файл:** [`config/articles.json`](config/articles.json) 🗑️ удалён

### 2. Graceful shutdown (SIGINT/SIGTERM)
- Добавлены обработчики сигналов в [`app.py`](app.py)
- Решает проблему зомби-процессов Python, блокировавших порт 5000

### 3. Health-check эндпоинт `GET /api/health`
- Проверяет доступность всех конфигурационных файлов
- **Файл:** [`app.py`](app.py)

### 4. Оптимизация загрузки API-ключа DeepSeek
- Удалена `_get_api_key()` из [`chat_routes.py`](src/routes/chat_routes.py)
- Ключ загружается один раз в `Config.DEEPSEEK_API_KEY`

### 5. Убрать `resetAllData()` из переключения вкладок
- Вкладки переключаются без сброса загруженных данных
- **Файл:** [`templates/index.html`](templates/index.html)

### 6. Архивация задач
- `completed_at` + 1ч → статус `archived`

### 7. Защита API-ключа в git
- `.gitignore` содержит `.env`

### 8. Логирование (logging вместо print)
- Ротация логов: 10 MB × 5 файлов

### 9. Починка кликабельности старых диалогов + CSP
- Разрешены CDN в CSP + блокировка диалогов при выключенном DeepSeek

### 10. Блокнот задач: новые задачи наверх + авто-даты

### 11. Исправление таймаута сессии (10 мин неактивности)

### 12. Скрытие фона при модалке логина

### 13. Всплывающие подсказки (`title`) для всех UI элементов
- Добавлены `title`-атрибуты при наведении курсора на кнопки, select'ы, input'ы и радио-кнопки
- **Исключение:** правая панель «Блокнот задач» (там всё интуитивно понятно)
- **Файл:** [`templates/index.html`](templates/index.html)

### 14. Persist `_temp_files` (In-memory → JSON)
- `_temp_files` больше не теряется при рестарте сервера
- **Файлы:** [`src/routes/constructor_routes.py`](src/routes/constructor_routes.py), [`config/constructor_temp_files.json`](config/constructor_temp_files.json)

### 15. Rate limiting / SESSION_COOKIE_SECURE / clean_old_uploads at startup
- Flask-Limiter (5/min на /api/login)
- SESSION_COOKIE_SECURE настраивается через .env
- clean_old_uploads вызывается внутри `create_app()` (работает и через wsgi.py)
- **Файлы:** [`app.py`](app.py), [`src/config.py`](src/config.py), [`requirements.txt`](requirements.txt)

### 16. Вынос планировщиков в отдельный модуль
- [`src/scheduler.py`](src/scheduler.py) — 3 планировщика (uploads, сессии, задачи) + graceful shutdown
- Удалены старые планировщики из app.py
- **Файлы:** [`src/scheduler.py`](src/scheduler.py), [`app.py`](app.py)

### 17. Code quality — TypedDict, константы, фильтрация, кэширование
- [`src/types.py`](src/types.py) — 6 TypedDict'ов
- Константы `AGG_COLUMN_NAME`, `DATE_PREFIXES` в constructor.py
- Единая `_apply_filters_to_df()` — 7 типов фильтров
- Кэширование DataFrame (cached_df) — ускорение повторных запросов
- MAX_HISTORY_MESSAGES=50 для DeepSeek
- Замена `except: pass` на `logger.warning` в 3 файлах
- `return` после `yield` ошибки в генераторе
- Импорт `re` на уровень модуля

### 18. Баг-фикс: очистка селектов сводной при "Сбросить"
- Кнопка "Сбросить" теперь полностью очищает `<option>` в селектах pivot
- **Файл:** [`templates/index.html`](templates/index.html:2642)

### 19. Вертикальный сайдбар вкладок (UI редизайн)
- Горизонтальные вкладки заменены на вертикальную панель слева (сайдбар)
- 3 группы: 📊 Excel (Конвертер, Профили, Справочники), 🔧 Анализ (Конструктор), 🤖 AI (DeepSeek)
- **CSS:** `.sidebar-tabs` (width:180px, border-right), `.sidebar-group`, `.sidebar-group-label`, `.tab-btn` (блочные, левый border-индикатор), `.sidebar-content` (flex:1)
- `.left-panel` → `display:flex; flex-direction:column`, `.container` → `display:flex; flex:1` для корректной высоты
- **Файл:** [`templates/index.html`](templates/index.html:28) (CSS), [`templates/index.html`](templates/index.html:250) (HTML)

### 20. 🐛 Баг-фикс: datetime в ключах словарей при загрузке листа в Конструкторе
- **Проблема:** `TypeError: '<' not supported between instances of 'datetime.datetime' and 'str'` при `jsonify()` после `load_sheet_data()` — ошибка сериализации JSON.
- **Корневая причина:** Excel-файл содержит колонки, заголовки которых — даты (напр. 1–31 мая 2026). При `pd.read_excel(dtype=str)` **openpyxl** возвращает заголовки колонок как `datetime.datetime`-объекты, а не строки. Эти объекты становятся **ключами словарей** после `to_dict(orient='records')`. Функция `_sanitize_for_json()` санитизировала только значения (`v`), но не ключи (`k`).
- **Исправление:**
  ```python
  # Было (ключи не санитизировались):
  if isinstance(obj, dict):
      return {k: _sanitize_for_json(v) for k, v in obj.items()}
  
  # Стало (ключи тоже санитизируются):
  if isinstance(obj, dict):
      return {_sanitize_for_json(k): _sanitize_for_json(v) for k, v in obj.items()}
  ```
- Также добавлены: обработка `np.datetime64` (не является подклассом `datetime.datetime`), `hasattr(obj, 'strftime')` для pandas.Timestamp, catch-all для любых не-JSON-типов.
- **Файл:** [`src/routes/constructor_routes.py`](src/routes/constructor_routes.py:42)
- **Статус:** ✅ Исправлено (2026-06-03)

### 21. 🐛 Баг-фикс: Декомпозиция дат — NaT-фильтрация + универсальный парсер `_parse_dates_flexible()` (03.06.2026)

**Проблема:** Две связанные проблемы в декомпозиции datetime-колонок:

**21а. NaT-фильтрация:** Четыре компонента (год/квартал/месяц/день) по-разному обрабатывали `NaT`-значения:
- Месяц (`__месяц__`): `fillna('')` → пустая строка ✅ корректно отфильтровывался
- Год (`__год__`): `fillna(0).astype(int).astype(str)` → `"0"` ❌ не отфильтровывался
- Квартал (`__квартал__`): `'Q' + fillna(0)` → `"Q0"` ❌ не отфильтровывался
- День (`__день__`): `fillna(0).str.zfill(2)` → `"00"` ❌ не отфильтровывался

**21б. Конфликт форматов дат (CRITICAL):** После добавления `dayfirst=True` в `decompose_date_column()` и `_infer_column_types()` — ISO-даты (например `2026-05-01`) парсились неверно: день=5, месяц=1 (Январь) вместо дня=1, месяца=5 (Май). Стандартный `pd.to_datetime()` с `dayfirst=True` интерпретирует `2026` как день, `05` как месяц — путаница для форматов, где год стоит первым.

**Исправление 21а:** [`src/services/constructor.py:207`](src/services/constructor.py:207) — `nat_mask` approach:
```python
nat_mask = dt_series.isna()
year_vals = dt_series.dt.year.fillna(0).astype(int).astype(str)
year_vals[nat_mask] = ''   # NaT → ''
```

**Исправление 21б:** [`src/services/constructor.py:113`](src/services/constructor.py:113) — Новая функция `_parse_dates_flexible()`:

```python
def _parse_dates_flexible(series: pd.Series) -> pd.Series:
    """
    Универсальный парсер дат, поддерживающий:
    - ISO-формат: 2026-05-01, 2026-05-01 15:12:16
    - Русский формат: 01.05.2026, 31.12.2026, 01/05/2026
    Алгоритм:
    1. По умолчанию парсим с dayfirst=True (для русского ДД.ММ.ГГГГ)
    2. Для значений, начинающихся с 4 цифр (ISO-формат 2026-...),
       перепарсиваем без dayfirst, чтобы избежать путаницы день/месяц
    """
    series_str = series.astype(str).str.strip()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        result = pd.to_datetime(series_str, errors='coerce', dayfirst=True)
    iso_mask = series_str.str.match(r'^\d{4}') & series_str.notna() & (series_str != '')
    if iso_mask.any():
        result[iso_mask] = pd.to_datetime(series_str[iso_mask], errors='coerce')
    return result
```

Функция используется в:
- [`_infer_column_types()`](src/services/constructor.py:186) — вместо `pd.to_datetime(series_str, errors='coerce', dayfirst=True)`
- [`decompose_date_column()`](src/services/constructor.py:209) — вместо `pd.to_datetime(series.astype(str), errors='coerce')`

**Проверка всех форматов:**

| Входное значение | Ожидание | day | month | Статус |
|-----------------|----------|-----|-------|--------|
| `2026-05-01` | ISO | 1 | 5 | ✅ |
| `01.05.2026` | RU ДД.ММ.ГГГГ | 1 | 5 | ✅ |
| `2026-05-01 15:12:16` | ISO с временем | 1 | 5 | ✅ |
| `31.12.2026` | RU ДД.ММ.ГГГГ | 31 | 12 | ✅ |
| `2026-5-1` | ISO короткий | 1 | 5 | ✅ |
| `01/05/2026` | RU с `/` | 1 | 5 | ✅ |
| `2026-05-14` | ISO | 14 | 5 | ✅ |
| `14.05.2026` | RU | 14 | 5 | ✅ |
| `недата` | Invalid | NaT | NaT | ✅ |
| `` | Empty | NaT | NaT | ✅ |
| `None` | None | NaT | NaT | ✅ |

### 22. ✨ Выбор режима итогов (totals_mode) для сводных таблиц (03.06.2026)

**Проблема:** Первоначально был только бинарный переключатель "📊 Итого" (вкл/выкл), который добавлял **сразу** и итоговую строку снизу, и итоговую колонку справа. Пользователю нужно было выбирать, где именно показывать итоги: только по строкам (колонка справа), только по столбцам (строка снизу), или вместе.

**Исправление (3 уровня):**

1. **Бэкенд** [`src/services/constructor.py:375`](src/services/constructor.py:375):
   - Параметр `show_totals: bool = False` → **`totals_mode: str = 'none'`** в сигнатуре `build_pivot_table()`
   - 4 режима:
     - `'none'` — без итогов (margins=False)
     - `'rows'` — только итоговая колонка справа (сумма по строкам)
     - `'cols'` — только итоговая строка снизу (сумма по столбцам)
     - `'both'` — и строка, и колонка (как старый `show_totals=True`)
   - **Для pivot с колонками:** `pd.pivot_table(..., margins=totals_mode in ('rows','cols','both'), margins_name='Итого')`, затем **пост-фильтрация** итоговых строк/колонок в зависимости от режима
   - **Для группировки без колонок:** ручной расчёт итоговой строки (`totals_mode in ('cols','both')`) и/или итоговой колонки (`totals_mode in ('rows','both')`)

2. **API** [`src/routes/constructor_routes.py:307`](src/routes/constructor_routes.py:307):
   - `show_totals = data.get('show_totals', False)` → **`totals_mode = data.get('totals_mode', 'none')`**
   - `build_pivot_table(totals_mode=totals_mode)`

3. **Фронтенд** [`templates/index.html:456`](templates/index.html:456):
   - iOS-style toggle switch → **4 segmented buttons** (radio-стиль с скрытыми инпутами):
     - 🚫 **Без итогов** (`'none'`) — оранжевый фон активен по умолчанию
     - 📊 **По строкам** (`'rows'`) — итоговая колонка справа
     - 📊 **По столбцам** (`'cols'`) — итоговая строка снизу
     - 📊 **По строкам и столбцам** (`'both'`) — оба итога
   - Функция `initTotalsToggle()` → **`updateTotalsModeStyle()`** — переключение активного стиля кнопки
   - При сборке pivot: чтение `document.querySelector('input[name="totalsMode"]:checked').value`
   - В API: `totals_mode: totalsMode` вместо `show_totals: showTotals`

**Поведение по режимам:**
| Режим | Итоговая колонка (справа) | Итоговая строка (снизу) |
|-------|--------------------------|------------------------|
| `'none'` | ❌ | ❌ |
| `'rows'` | ✅ Сумма значений по каждой строке | ❌ |
| `'cols'` | ❌ | ✅ Сумма значений по каждой колонке |
| `'both'` | ✅ | ✅ |

**Технические детали пост-фильтрации:**
- После `pd.pivot_table()` с `margins=True` удаляем лишние строки/колонки по маске
- Маска колонок: `[c.endswith(' | Итого') for c in flat_cols]`
- Маска строк: проверка `pivot[rc].astype(str) == 'Итого'` для каждой row-колонки
- Для группировки без колонок: `pivot[итого_col_name] = pivot[val_cols_in_pivot].sum(axis=1).round(2)`

### 23. ✨ UI редизайн: segmented buttons для "📊 Итого" + "Плоский/Иерархический" (03.06.2026)

**Проблема:** Три элемента управления в конструкторе (чекбокс/тоггл "📊 Итого" + два радио-инпута "📐 Плоский" / "📋 Иерархический") выглядели некрасиво и не соответствовали современному UI/UX. Кроме того, бинарный переключатель не позволял выбрать конкретный тип итогов.

**Исправление:** [`templates/index.html:456`](templates/index.html:456) — полная замена визуального стиля на segmented buttons:

**23а. Segmented buttons для "📊 Итого" (4 режима):**
```html
<div style="display:flex; gap:0; border-radius:6px; overflow:hidden; border:1px solid #ffe0b2; font-size:12px;">
    <label id="totalsNoneLabel" style="cursor:pointer; padding:4px 10px; background:#ff9800; color:white; ...">
        <input type="radio" name="totalsMode" value="none" checked onchange="updateTotalsModeStyle()" style="display:none;">
        <span>🚫</span> Без итогов
    </label>
    <label id="totalsRowsLabel" style="cursor:pointer; padding:4px 10px; background:#f5f5f5; color:#666; ...">
        <input type="radio" name="totalsMode" value="rows" onchange="updateTotalsModeStyle()" style="display:none;">
        <span>📊</span> По строкам
    </label>
    <label id="totalsColsLabel" style="...">
        <input type="radio" name="totalsMode" value="cols" onchange="updateTotalsModeStyle()" style="display:none;">
        <span>📊</span> По столбцам
    </label>
    <label id="totalsBothLabel" style="...">
        <input type="radio" name="totalsMode" value="both" onchange="updateTotalsModeStyle()" style="display:none;">
        <span>📊</span> По строкам и столбцам
    </label>
</div>
```

**Логика `updateTotalsModeStyle()`** (JS):
- Активная кнопка: оранжевый фон (`#ff9800`), белый текст, жирный шрифт
- Неактивная: серый фон (`#f5f5f5`), серый текст (`#666`), средний вес
- Цвета для каждого режима:
  - `'none'`: `#ff9800` (оранжевый)
  - `'rows'`: `#ff7043` (оранжево-красный)
  - `'cols'`: `#ef5350` (красный)
  - `'both'`: `#d32f2f` (тёмно-красный)

**23б. Segmented buttons для "📐 Плоский" / "📋 Иерархический":** (без изменений)
```html
<div style="display:flex; gap:0; border-radius:6px; overflow:hidden; border:1px solid #c8e6c9; font-size:12px;">
    <label id="formatFlatLabel" style="...">
        <input type="radio" name="outputFormat" value="flat" checked onchange="updateOutputFormatStyle2()" style="display:none;">
        <span>📐</span> Плоский
    </label>
    <label id="formatHierarchicalLabel" style="...">
        <input type="radio" name="outputFormat" value="hierarchical" onchange="updateOutputFormatStyle2()" style="display:none;">
        <span>📋</span> Иерархический
    </label>
</div>
```

**Визуальные разделители:** Между тремя группами кнопок (Построить | Итого | Формат) добавлены `|` (<span style="color:#ddd; font-size:18px; user-select:none;">)

### 24. ✨ Автоопределение строки заголовков (header_row) + диалог выбора (03.06.2026)

**Проблема:** `pd.read_excel()` всегда использовал `header=0` (первая строка — заголовки колонок). В файлах, где заголовки находились в строке 1 (0-индексированная) или вообще отсутствовали, все колонки отображались как `Unnamed: 0`, `Unnamed: 1` и т.д. Из 8 листов файла `НМ Май .xlsx` только 1 имел корректные заголовки в строке 0.

**Исправление (6 уровней):**

**24а. Новая функция `_detect_header_row()`** [`src/services/constructor.py:42`](src/services/constructor.py:42):
```python
def _detect_header_row(file_path: str, sheet_name: str) -> Dict[str, Any]:
```
- Читает первые 10 строк без заголовков (`header=None`)
- Считает количество `Unnamed` колонок для каждой строки-кандидата (0..9)
- Выбирает строку с минимальным количеством `Unnamed` колонок
- Дополнительно проверяет: если в выбранной строке есть пустые ячейки, а в следующей — ещё меньше `Unnamed`, берёт следующую
- Возвращает: `{'header_row': int, 'rows': List[List], 'needs_review': bool}`
- `needs_review=True`, если лучшая строка всё равно содержит `Unnamed` колонки (значит, не удалось определить однозначно)

**24б. Модификация `load_sheet_data()`** [`src/services/constructor.py:125`](src/services/constructor.py:125):
- Новый параметр `header_row: int = 0` — явное указание строки заголовков
- Новый параметр `transpose: bool = False` — поддержка транспонированных данных
- При `transpose=True`: читает с `header=None`, транспонирует `df.T`, использует первую строку после транспонирования как заголовки
- Если `header_row` не указан — использует `_detect_header_row()` для автоопределения

**24в. Новая функция `_infer_column_types_from_df()`** [`src/services/constructor.py:302`](src/services/constructor.py:302):
- Инлайн-определение типов колонок на основе уже загруженного DataFrame (без повторного чтения файла)
- Используется для транспонированных данных, где нельзя просто перечитать файл с другим `header`

**24г. Модификация `apply_filters()` и `build_pivot_table()`** [`src/services/constructor.py`](src/services/constructor.py):
- Обе функции получили параметр `header_row: int = 0`
- Передаётся в `pd.read_excel(header=header_row)` при загрузке данных из файла

**24д. Новый API-эндпоинт** [`src/routes/constructor_routes.py:251`](src/routes/constructor_routes.py:251):
```
POST /api/constructor/detect_headers
```
- Принимает: `{file_id, sheet_name}`
- Вызывает `_detect_header_row()`, возвращает `{header_row, rows (первые 10 строк для предпросмотра), needs_review}`

**24е. UI-диалог** [`templates/index.html:242`](templates/index.html:242) — новый HTML-модал:
```html
<div id="constructorHeaderDialog" style="display:none; ...">
```
- **Таблица предпросмотра:** показывает первые 10 строк файла, строка заголовка выделяется фоном
- **Радио-кнопки выбора строки:** для каждой строки (0..9) — radio input с номером строки
- **Чекбокс транспонирования:** `constructorTransposeCheckbox` — переключатель `transpose`
- **Кнопки:** "✅ Применить" (confirmHeaderDialog) / "❌ Отмена" (closeHeaderDialog)
- **JS-переменные:** `constructorSheetHeaderConfig` (пер-листовые настройки), `_pendingHeaderData` (временное хранилище для диалога)
- **Функции:** `showHeaderDialog()`, `closeHeaderDialog()`, `updateHeaderRowChoice()`, `confirmHeaderDialog()`, `loadConstructorSheetData()`
- **Обновлённый `constructorLoadSheetBtn`:** сначала вызывает `/api/constructor/detect_headers`, если `needs_review` — показывает диалог, иначе загружает сразу с авто-определённой строкой
- **Per-sheet кэширование:** после выбора настройки сохраняются в `constructorSheetHeaderConfig[sheetName] = {header_row, transpose}` — пользователь не спрашивается повторно для того же листа

**24ж. Проброс `header_row` в JS-вызовы:**
- **Preview** (`/api/constructor/preview`): добавлено `header_row: (constructorSheetHeaderConfig[constructorCurrentSheet]?.header_row) || 0`
- **Pivot** (`/api/constructor/pivot`): добавлено `header_row: (constructorSheetHeaderConfig[constructorCurrentSheet]?.header_row) || 0`
- **Сценарии:** при сохранении — `params.header_row` и `params.transpose`; при загрузке — `applyScenario()` восстанавливает их в `constructorSheetHeaderConfig`

**Сценарии работы:**
| Сценарий | needs_review | Поведение |
|----------|-------------|-----------|
| Заголовки в строке 0, без `Unnamed` | `false` | Авто-загрузка без диалога |
| Заголовки в строке 1, строка 0 — пустая/служебная | `true` | Диалог: строка 1 предвыбрана |
| Все строки содержат `Unnamed` (нет заголовков) | `true` | Диалог: строка 0 предвыбрана |
| Транспонированные данные (строки → колонки) | `true` | Диалог + чекбокс транспонирования |

### 25. ✨ Поддержка транспонированных данных (transpose) (03.06.2026)

**Проблема:** Некоторые Excel-файлы хранят данные в транспонированном виде — колонки расположены по строкам, а строки — по колонкам. Например, таблица где первая колонка содержит названия показателей, а даты (месяцы/кварталы) расположены горизонтально в первой строке.

**Решение:**
- Параметр `transpose: bool = False` в `load_sheet_data()`
- При `True`: читает Excel с `header=None`, затем `df = df.T`, первая строка становится заголовками
- UI-диалог позволяет включить транспонирование через чекбокс перед загрузкой листа
- Настройка `transpose` сохраняется в `constructorSheetHeaderConfig` и восстанавливается из сценариев

**Техническая деталь:** После транспонирования тип данных теряется (все значения становятся строками). Для восстановления типов используется `_infer_column_types_from_df()` вместо `_infer_column_types()` (которая читает файл заново).

### 26. ✨ Кликабельные ссылки в тексте задач (04.06.2026)

**Проблема:** URL-адреса в тексте задач (например, ссылки на задачи из других сервисов) отображались как обычный текст, их нельзя было открыть кликом.

**Исправление:** [`templates/index.html`](templates/index.html:1620):
- Добавлена функция [`linkifyText(text)`](templates/index.html:1620) — находит URL (`https://...`) в тексте и оборачивает в `<a href="..." target="_blank" rel="noopener noreferrer">` с синим цветом и подчёркиванием
- Применена как в [`renderTaskItem()`](templates/index.html:1668) (архив/отменено), так и в рендере активных задач ([строка 1709](templates/index.html:1709))

### 27. ✨ Свёртывание групп в Архив/Отменено + счётчик задач (04.06.2026)

**Проблема:** В архиве и отменённых задачах группы отображались всегда развёрнутыми. При большом количестве задач было неудобно пролистывать, и не было видно, сколько задач в группе.

**Исправление:** [`templates/index.html`](templates/index.html):
- **Заголовки групп стали кликабельными** — при клике содержимое группы сворачивается/разворачивается
- **Счётчик задач в заголовке** — отображается в сером бейдже с разделителем `•`, например: `📆 июнь 2026 • [3 задачи]`
- **CSS:** `.task-group-header.collapsed`, `.task-group-content`, `.toggle-icon`, `.group-title-separator`, `.task-count-badge`
- Функция [`getTaskCountLabel(count)`](templates/index.html:1628) — правильное склонение: «1 задача», «2 задачи», «5 задач»

### 28. ✨ Счётчик задач в разделе «Активно» (04.06.2026)

**Проблема:** В разделе активных задач не было видно, сколько всего задач, сколько выполнено и сколько осталось.

**Исправление:** [`templates/index.html`](templates/index.html:737):
- Добавлен элемент `#activeTaskCounter` под строкой добавления задачи
- Отображает: `📋 Всего: 5 | ✅ Выполнено: 2 | ⏳ Осталось: 3`
- Автоматически обновляется в [`renderTaskList()`](templates/index.html:1736) при каждой загрузке задач

### 29. ✨ Автообновление через GitHub Releases (04.06.2026)

**Задача:** Добавить механизм автоматической проверки и установки обновлений через GitHub Releases.

**Созданные файлы:**
- [`version.json`](version.json) — файл с текущей версией и именем репозитория `Dgigin/Personal-assistant`
- [`src/updater.py`](src/updater.py:1) — модуль с функциями:
  - `get_current_version()` — читает версию из `version.json`
  - `check_for_update()` — GET к `https://api.github.com/repos/{repo}/releases/latest`, сравнивает версии
  - `download_update(url, progress_callback)` — скачивает ZIP во временную папку с callback прогресса
  - `install_update(zip_path)` — создаёт `update.bat`, который через 3 сек распаковывает архив и перезапускает сервер
  - `check_pending_update()` — очищает мусор от прерванных обновлений при старте
- [`src/routes/update_routes.py`](src/routes/update_routes.py:1) — 4 эндпоинта:
  - `GET /api/check_update` — проверка наличия обновления
  - `GET /api/check_update/status` — статус текущего процесса (прогресс скачивания)
  - `POST /api/apply_update` — запуск скачивания и подготовки обновления
  - `POST /api/apply_update/restart` — запуск `update.bat` и перезапуск сервера

**Изменённые файлы:**
- [`app.py`](app.py:29) — импорт `update_bp`, регистрация blueprint, вызов `check_pending_update()` при старте, добавление эндпоинтов обновлений в исключения аутентификации (чтобы проверка работала без логина)
- [`templates/index.html`](templates/index.html) — добавлены:
  - CSS-стили для `#updateBanner` (жёлтый баннер с тенью, анимация `slideInUp`), `#versionIndicator` (правый нижний угол), прогресс-бар
  - HTML: `#updateBanner` с заголовком, описанием, кнопками и прогресс-баром; `#versionIndicator` с цветной точкой и текстом версии
  - JS-функции: `initUpdateSystem()`, `checkForUpdates()` (периодическая проверка раз в 6 часов), `showUpdateBanner()`, `startUpdate()`, `pollUpdateProgress()` (опрос статуса каждую секунду), `restartForUpdate()`, `formatBytes()`

**Принцип работы:**
1. При загрузке страницы — `initUpdateSystem()` вызывает `checkForUpdates()`
2. Если на GitHub есть новый релиз — показывается жёлтый баннер с кнопкой "Обновить"
3. При клике — `POST /api/apply_update` → скачивание ZIP (прогресс отображается в реальном времени)
4. После скачивания — кнопка "🔄 Перезапустить сейчас"
5. `update.bat` ждёт 3 сек, распаковывает архив поверх текущей директории, удаляет временные файлы и запускает `python app.py`

### 30. ✨ Установщик (Inno Setup) (04.06.2026)

**Задача:** Создать скрипт Inno Setup для сборки установщика Windows.

**Созданные файлы:**
- [`installer.iss`](installer.iss:1) — скрипт Inno Setup:
  - Устанавливает в `%ProgramFiles%\ExcelConverter`
  - Ярлыки: меню Пуск, рабочий стол (опционально)
  - Упаковка: `app.py`, `wsgi.py`, `requirements.txt`, `version.json`, `README.md`, `.env.example` (НЕ `.env`!), `setup_env.py`, все `src/*.py`, `templates/*`
  - **ВНИМАНИЕ:** `config/*.json` и `profiles/*.json` НЕ копируются — каждый гость получает чистые данные
  - `[Dirs]` — создаёт все папки в `%APPDATA%\Excel Converter` (config, profiles, uploads, logs, temp)
  - После установки: запускает `install_deps.bat` (pip install -r requirements.txt → создаёт .env с уникальным SECRET_KEY)
  - Проверка наличия Python при старте установщика

- [`run.bat`](run.bat:1) — запуск приложения с автоустановкой зависимостей (вызывает `setup_env.py` для создания .env)
- [`install_deps.bat`](install_deps.bat:1) — установка Python-зависимостей (вызывает `setup_env.py` для создания .env)
- [`setup_env.py`](setup_env.py:1) — скрипт генерации .env с уникальным SECRET_KEY (v1.0.3)

**Сборка установщика:**
```
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```
Готовый файл: `Output/ExcelConverter-Setup-1.0.5.exe`

### 31. 🐛 Критический багфикс: update.bat (04.06.2026)

**Проблема:** `install_update()` в [`updater.py`](src/updater.py:317) генерировал `update.bat`, который использовал `tar -xf` (отсутствует на некоторых Windows) и `PowerShell Expand-Archive` (ошибка "Not enough memory" в Program Files). При обновлении v1.0.2→v1.0.3 `update.bat` падал, не успевал удалить себя (`del "%~f0"`), и при каждом перезапуске сервера запускался снова, показывая ту же ошибку.

**Решение (v1.0.4):**
- Добавлен `_create_apply_script()` — генерирует `apply_update.py`, который распаковывает ZIP через Python `zipfile.ZipFile` (гарантированно доступен)
- `update.bat` теперь просто вызывает `python apply_update.py <zip> <target>`

**Решение (v1.0.5):**
- В [`run.bat`](run.bat:13) добавлена очистка stale файлов при старте:
  ```batch
  if exist "%~dp0update.bat" del "%~dp0update.bat"
  if exist "%~dp0apply_update.py" del "%~dp0apply_update.py"
  if exist "%~dp0update_pending.flag" del "%~dp0update_pending.flag"
  ```
- В [`app.py`](app.py:74) подавлены логи Werkzeug в консоли:
  ```python
  logging.getLogger('werkzeug').setLevel(logging.WARNING)
  ```

**Решение (v1.0.6):**
- Из [`update.bat`](src/updater.py:337) убрана строка `del "%~f0"` — Windows не может удалить запущенный batch-файл, что вызывало ошибку `"The batch file cannot be found. Not enough memory resources..."`. Теперь очистка stale `update.bat` полностью возложена на [`run.bat`](run.bat) при следующем запуске.
- В [`app.py`](app.py:77) уровень логгера Werkzeug повышен с `WARNING` до `ERROR`, чтобы подавить сообщение `"WARNING: This is a development server"` (логируется на `INFO`):
  ```python
  logging.getLogger('werkzeug').setLevel(logging.ERROR)
  ```

**Выпущенные релизы:**
| Версия | Дата | Ссылка |
|--------|------|--------|
| v1.0.4 | 04.06.2026 | https://github.com/Dgigin/Personal-assistant/releases/tag/v1.0.4 |
| v1.0.5 | 04.06.2026 | https://github.com/Dgigin/Personal-assistant/releases/tag/v1.0.5 |
| v1.0.6 | 04.06.2026 | https://github.com/Dgigin/Personal-assistant/releases/tag/v1.0.6 |

### 32. 📦 Итоговый список файлов (04.06.2026)

```
f:/excel_converter/
├── version.json              # Версия приложения + репозиторий GitHub
├── run.bat                   # Запуск с автоустановкой зависимостей
├── install_deps.bat          # Установка зависимостей
├── setup_env.py              # Генератор .env с уникальным SECRET_KEY (v1.0.3)
├── installer.iss             # Inno Setup скрипт
├── .env.example              # Шаблон .env (SECRET_KEY=__GENERATE_ME__)
├── update.bat                # (создаётся динамически при обновлении)
├── src/
│   ├── updater.py            # Модуль проверки/скачивания/установки обновлений
│   └── routes/
│       └── update_routes.py  # API-эндпоинты обновлений
```

---

# План улучшений: Новый функционал, производительность, безопасность и UI/UX

> **Дата:** 2026-06-03
> **Проект:** excel_converter
> **Цель:** Детальная оценка и план реализации предложенных улучшений

---

## 📋 Оглавление

1. [Оценка выполнимости](#-оценка-выполнимости)
2. [Фаза 0 — Быстрые победы (1-2 дня)](#️-фаза-0--быстрые-победы-1-2-дня)
3. [Фаза 1 — Тестирование и качество кода (3-5 дней)](#-фаза-1--тестирование-и-качество-кода-3-5-дней)
4. [Фаза 2 — Производительность и масштабирование (5-7 дней)](#-фаза-2--производительность-и-масштабирование-5-7-дней)
5. [Фаза 3 — Новый функционал (7-10 дней)](#-фаза-3--новый-функционал-7-10-дней)
6. [Фаза 4 — Безопасность (1-2 дня)](#-фаза-4--безопасность-1-2-дня)
7. [Фаза 5 — UI/UX (3-5 дней)](#-фаза-5--uiux-3-5-дней)
8. [Фаза 6 — Мониторинг и отладка (2-3 дня)](#-фаза-6--мониторинг-и-отладка-2-3-дня)
9. [Итоговая смета и рекомендации](#-итоговая-смета-и-рекомендации)

---

## 💎 Оценка выполнимости

**Общая оценка: ВЫПОЛНИМО на 95%.**

Проект уже имеет **отличную архитектурную базу**:
- Чистое разделение на `routes/` (контроллеры) и `services/` (бизнес-логика)
- TypedDict-схемы в [`src/types.py`](src/types.py)
- Blueprint-регистрация в [`app.py`](app.py)
- Вынесенный планировщик в [`src/scheduler.py`](src/scheduler.py)
- Сервер-сайд сессии с таймаутами

**Что упрощает реализацию:**

| Предложение | Уже есть в проекте |
|-------------|-------------------|
| `MAX_CONTENT_LENGTH` | ✅ Уже задан 50 MB в [`src/config.py:34`](src/config.py:34) |
| `secure_filename` | ✅ Уже используется в [`constructor_routes.py:186`](src/routes/constructor_routes.py:186) |
| Линтеры | Вручную частично проведены — TypedDict, константы, `except:pass` → logger |
| Экспорт CSV | Частично — API для pivot возвращает JSON, фронтенд может сформировать CSV |
| Пагинация | Уже есть `limit`/`offset` в [`apply_filters()`](src/services/constructor.py:483) |

---

## 🛡️ Фаза 0 — Быстрые победы (1-2 дня)

### 0.1 ✅ Экспорт сводной в CSV напрямую

**Где:** [`constructor_routes.py:397`](src/routes/constructor_routes.py:397) — `download_result()`

**Что сделать:** Добавить параметр `format: 'xlsx' | 'csv'` в POST `/api/constructor/download`.

**Бэкенд:**
```python
# в download_result()
output_format = data.get('format', 'xlsx')
if output_format == 'csv':
    import csv, io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(pivot_data)
    # вернуть как file stream или сохранить временный .csv
```

**Фронтенд:** Рядом с кнопкой "Скачать XLSX" добавить "📋 CSV" → вызывает тот же endpoint с `format: 'csv'`.

**Сложность:** 🟢 Низкая (0.5 дня)

### 0.2 ✅ Тёмная тема (CSS-переключатель + localStorage)

**Где:** Весь [`templates/index.html`](templates/index.html) — CSS-переменные.

**Что сделать:**
1. Определить CSS-переменные для цветов (фон, текст, границы, кнопки)
2. Переключатель в шапке или сайдбаре (🌙/☀️)
3. Сохранение в `localStorage.theme`

```css
:root { --bg: #f0f2f5; --card-bg: white; --text: #333; }
[data-theme="dark"] { --bg: #1a1a2e; --card-bg: #16213e; --text: #e0e0e0; }
body { background: var(--bg); color: var(--text); }
```

**Сложность:** 🟢 Низкая (0.5 дня)

### 0.3 ✅ Горячие клавиши

**Где:** [`templates/index.html`](templates/index.html) — JS.

**Что сделать:** Добавить `document.addEventListener('keydown', ...)`:
- `Ctrl+Enter` — построить сводную (клик по `constructorBuildPivotBtn`)
- `Ctrl+S` — сохранить сценарий (клик по `constructorSaveScenarioBtn`)

**Сложность:** 🟢 Низкая (0.25 дня)

### 0.4 ✅ Ограничение размера файла + дружелюбная ошибка

**Где:** [`src/config.py:34`](src/config.py:34) — **уже есть** `MAX_CONTENT_LENGTH = 50 * 1024 * 1024`.

**Что осталось:** Добавить обработку `413 Request Entity Too Large` в [`app.py`](app.py):

```python
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'Файл слишком большой. Максимальный размер: 50 МБ.'}), 413
```

**Сложность:** 🟢 Низкая (0.25 дня)

### Итого Фаза 0: **~1.5 дня**

---

## 🧪 Фаза 1 — Тестирование и качество кода (3-5 дней)

### 1.1 Юнит-тесты для [`constructor.py`](src/services/constructor.py)

**Где:** Новый файл `tests/test_constructor.py`.

**Критические функции для тестирования:**

| Функция | Что тестировать | Приоритет |
|---------|----------------|-----------|
| `_parse_dates_flexible()` | ISO (2026-05-01), RU (01.05.2026), NaT, пустые, mixed-форматы | 🔴 CRITICAL |
| `_infer_column_types()` | number > date > text priority, unnamed-колонки, пустые колонки | 🔴 CRITICAL |
| `decompose_date_column()` | NaT → '' для всех 4 компонентов | 🟠 HIGH |
| `_apply_filters_to_df()` | equals, contains, greater_than, is_empty — регистронезависимость | 🟠 HIGH |
| `build_pivot_table()` | multi-aggregation, hierarchical format, totals_mode | 🟡 MEDIUM |
| `save_scenario()` / `load_scenario()` | JSON read/write, кириллица в именах | 🟡 MEDIUM |
| `_detect_header_row()` | Лучшая строка среди 0..3, unnamed ratio | 🟡 MEDIUM |

**Пример теста:**
```python
def test_parse_dates_flexible_iso():
    s = pd.Series(['2026-05-01', '2026-05-14', 'недата', ''])
    result = _parse_dates_flexible(s)
    assert result.iloc[0].month == 5  # месяц = Май
    assert result.iloc[0].day == 1    # день = 1
    assert result.iloc[2] is pd.NaT  # недата → NaT
```

**Mock-объекты:** `pd.read_excel` через `unittest.mock.patch` или временные файлы.

### 1.2 Интеграционные тесты API

**Где:** Новый файл `tests/test_api_constructor.py`.

**Что тестировать:**
- `POST /api/constructor/upload` — загрузка .xlsx и .xls, проверка расширения
- `POST /api/constructor/pivot` — корректный pivot, ошибка без rows/values
- `POST /api/constructor/scenario/save` — создание, обновление, кириллица
- `POST /api/constructor/download` — скачивание XLSX
- Regression: datetime в ключах словарей (баг-фикс #20)
- Regression: NaT-фильтрация (баг-фикс #21)

**Инструмент:** `pytest` + Flask test client.

```python
def test_pivot_regression_datetime_keys(client, tmp_xlsx_with_date_headers):
    """Проверяет, что datetime-заголовки колонок не ломают jsonify."""
    upload_resp = client.post('/api/constructor/upload', data={'file': tmp_xlsx_with_date_headers})
    file_id = upload_resp.get_json()['file_id']
    # ... загрузка листа, построение pivot — не должно быть 500 ошибки
```

### 1.3 Требования для разработки (`requirements-dev.txt`)

Новый файл `requirements-dev.txt`:

```
# Тестирование
pytest>=8.0
pytest-flask>=1.3
pytest-cov>=5.0

# Линтеры и форматтеры
black>=24.0
ruff>=0.4
mypy>=1.10

# Типы для mypy
pandas-stubs>=2.2
types-requests>=2.31
```

**Дополнительно:** `pyproject.toml` с настройками:
```toml
[tool.black]
line-length = 120

[tool.ruff]
line-length = 120
target-version = "py311"
select = ["E", "F", "W", "I", "N", "UP"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 1.4 Docker-контейнеризация

**Где:** `Dockerfile` + `docker-compose.yml` в корне проекта.

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "-m", "waitress", "--host=0.0.0.0", "--port=5000", "wsgi:application"]
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./config:/app/config
      - ./uploads:/app/uploads
      - ./logs:/app/logs
      - ./profiles:/app/profiles
    env_file:
      - .env
    restart: unless-stopped
```

**Сложность:** 🟡 Средняя (1 день на docker, 3 дня на тесты)

### Итого Фаза 1: **~4 дня**

---

## ⚡ Фаза 2 — Производительность и масштабирование (5-7 дней)

### 2.1 Асинхронная обработка (Celery + Redis)

**Проблема:** POST `/api/constructor/pivot` выполняется синхронно. При файле 100+ МБ или сложной сводной пользователь ждёт.

**Архитектура:**

```
Flask (POST /api/constructor/pivot)
  → создаёт task_id, сохраняет в Redis/Pending
  → возвращает {task_id, status: 'pending'}
  → Celery worker выполняет build_pivot_table()
  → Flask (GET /api/constructor/task/<id>) возвращает статус
```

**Новые файлы:**
- `src/tasks.py` — Celery-задачи
- `src/celery_app.py` — конфигурация Celery (Redis broker)
- `src/routes/task_routes_v2.py` — endpoint GET /api/constructor/task/<id>

**Изменения:**
- [`constructor_routes.py:332`](src/routes/constructor_routes.py:332): `pivot_table()` — если файл > N строк → запускает Celery task
- [`src/services/constructor.py`](src/services/constructor.py): `build_pivot_table()` остаётся синхронной, но вызывается из Celery

**Зависимости:** `celery>=5.4`, `redis>=5.0`

**docker-compose.yml** (дополнение):
```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  worker:
    build: .
    command: celery -A src.celery_app worker --loglevel=info
    depends_on:
      - redis
    volumes: *app_volumes
```

### 2.2 Веб-сокеты для прогресса (Flask-SocketIO)

**Проблема:** Вместо polling (опрос статуса каждые N сек) — стриминг прогресса.

**Что сделать:**
1. Добавить `flask-socketio` в зависимости
2. При старте Celery-задачи — создать SocketIO room по `task_id`
3. Celery-задача шлёт события: `{'progress': 30, 'message': 'Читаю файл...'}`
4. Фронтенд: `socket.on('task_progress', ...)` — обновляет прогресс-бар

**Изменения:**
- [`app.py`](app.py): `SocketIO(app, cors_allowed_origins="*")`
- [`templates/index.html`](templates/index.html): + `<script src="/socket.io/socket.io.js">` + JS-обработчики
- `src/tasks.py`: вызов `socketio.emit()` через `SocketIO` instance

**Альтернатива:** Если Celery кажется избыточным — использовать `BackgroundScheduler` из APScheduler (уже в проекте) или `threading` для фоновых задач.

### 2.3 Пагинация / виртуальная прокрутка

**Проблема:** Сейчас `limit=100, offset=0`. Пользователь не может увидеть данные дальше первой сотни строк.

**Что уже есть:** [`apply_filters()`](src/services/constructor.py:483) уже поддерживает `limit` и `offset`.

**Что сделать на фронтенде:**
1. Добавить элементы управления пагинацией:
   - Кнопки "◀ Пред." / "След. ▶"
   - Индикатор "Строки X-Y из N"
   - Выбор размера страницы (25/50/100/200)
2. При нажатии "▶" — запрос `POST /api/constructor/preview` с `offset+=limit`

**Модификация** [`templates/index.html`](templates/index.html):
```javascript
let constructorPageOffset = 0;
const constructorPageLimit = 100;

function loadConstructorPage(direction) {
    if (direction === 'next') constructorPageOffset += constructorPageLimit;
    else constructorPageOffset = Math.max(0, constructorPageOffset - constructorPageLimit);
    // ... POST /api/constructor/preview с offset=constructorPageOffset
}
```

**Сложность:** 🟡 Средняя (2 дня на Celery, 1 день на сокеты, 1 день на пагинацию)

### Итого Фаза 2: **~6 дней**

---

## 🧠 Фаза 3 — Новый функционал (7-10 дней)

### 3.1 Вычисляемые поля (Custom columns)

**Проблема:** Пользователь хочет группировать по выражению: `left(Наименование, 3)` или `if возраст < 18 then "ребёнок"`.

**Решение:** Безопасный мини-язык выражений через `pd.eval()` с белым списком функций.

**Бэкенд** — новый файл `src/services/formula_engine.py`:

```python
import pandas as pd
import re

# Белый список разрешённых функций
ALLOWED_FUNCS = {
    'left': lambda s, n: s.str[:n],
    'right': lambda s, n: s.str[-n:],
    'mid': lambda s, pos, n: s.str[pos-1:pos-1+n],
    'len': lambda s: s.str.len(),
    'upper': lambda s: s.str.upper(),
    'lower': lambda s: s.str.lower(),
    'trim': lambda s: s.str.strip(),
    'if': lambda cond, t, f: pd.Series(np.where(cond, t, f)),
    'year': pd.Series.dt.year,
    'month': pd.Series.dt.month,
    'quarter': pd.Series.dt.quarter,
}

def safe_eval(expression: str, df: pd.DataFrame) -> pd.Series:
    """Безопасно вычисляет выражение над DataFrame.
    Поддерживает: col_name, ALLOWED_FUNCS, операторы сравнения, арифметику."""
    # 1. Парсим AST-дерево через pd.eval с запретом __import__, eval, exec
    # 2. Проверяем, что все имена колонок — существующие
    # 3. Вычисляем
    ...
```

**UI:** Простой редактор формул с текстовым полем + кнопка "➕ Добавить вычисляемое поле". Результат отображается как новая колонка в мультиселектах.

**Сложность:** 🟠 Высокая (2-3 дня)

### 3.2 Экспорт в PDF с графиками

**Новые зависимости:** `matplotlib>=3.8`, `reportlab>=4.1` (или `weasyprint`).

**Бэкенд** — новый endpoint `POST /api/constructor/export_pdf`:

```python
import matplotlib.pyplot as plt
from io import BytesIO
import base64

def generate_pdf_report(pivot_data, columns):
    # 1. Строим сводную таблицу
    # 2. Строим столбчатую диаграмму по первым 2-3 рядам
    # 3. Генерируем PDF (Matplotlib + ReportLab или через HTML + WeasyPrint)
    ...
```

**UI:** Кнопка "📄 PDF-отчёт" рядом с "Скачать XLSX".

**Сложность:** 🟠 Высокая (2-3 дня)

### 3.3 Версионирование сценариев

**Проблема:** Сейчас сценарии перезаписываются. Нужна история изменений.

**Решение:** Хранить версии как `scenario_v1.json`, `scenario_v2.json` или вложенные в `scenario_name/`.

**Изменения** в [`constructor.py:941`](src/services/constructor.py:941):

```python
def save_scenario_versioned(name, params):
    version_dir = os.path.join(SCENARIOS_DIR, secure_filename_for_scenario(name))
    os.makedirs(version_dir, exist_ok=True)
    version = len(os.listdir(version_dir)) + 1
    filename = f'{name}_v{version}.json'
    ...
```

**API:**
- `GET /api/constructor/scenario/versions?name=...` — список версий
- `POST /api/constructor/scenario/rollback` — откат к версии

**Сложность:** 🟡 Средняя (1 день)

### 3.4 Поддержка CSV

**Проблема:** Сейчас только .xlsx/.xls. Нужен детектор кодировки и разделителя.

**Изменения** в [`constructor.py:99`](src/services/constructor.py:99) — `load_excel_file()`:

```python
def load_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.csv':
        import chardet, csv
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read(100000))
        encoding = result['encoding']
        with open(file_path, 'r', encoding=encoding) as f:
            dialect = csv.Sniffer().sniff(f.read(1024))
            f.seek(0)
            df = pd.read_csv(f, dialect=dialect, encoding=encoding)
        ...
    else:
        # существующая логика Excel
```

**Зависимости:** `chardet>=5.2`

**Сложность:** 🟡 Средняя (1-2 дня)

### 3.5 Интеграция с Яндекс.Диск / Google Drive

**Архитектура:**
- Пользователь авторизуется через OAuth (Yandex/Google)
- Получает список файлов из облака
- Выбирает файл → приложение скачивает по API → обрабатывает

**Новые файлы:**
- `src/services/cloud_integration.py` — общий интерфейс
- `src/routes/cloud_routes.py` — endpoints для OAuth и списка файлов

**Сложность:** 🟠 Высокая (3-4 дня, в основном из-за OAuth-настройки)

### Итого Фаза 3: **~8 дней**

---

## 🔐 Фаза 4 — Безопасность (1-2 дня)

### 4.1 CSRF-защита (Flask-WTF)

**Что уже есть:** [`app.py:89-91`](app.py:89-91) — `SESSION_COOKIE_SAMESITE='Lax'` + проверка `Content-Type` в `chat_routes.py`.

**Что добавить:**
```python
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect()
csrf.init_app(app)
```

**Для API-эндпоинтов (POST/PUT/DELETE):** Добавить `_csrf_token` в тело запроса или заголовок `X-CSRFToken`.

**Важно:** CSRF-токен нужно генерировать на фронтенде (через мета-тег или JS-переменную). Для SPA без шаблонов — через отдельный endpoint `GET /api/csrf_token`.

**Сложность:** 🟡 Средняя (1 день)

### 4.2 Санация имён файлов

**Что уже есть:** [`constructor_routes.py:186`](src/routes/constructor_routes.py:186) — `secure_filename(file.filename)`.

**Что проверить:**
- Все ли места загрузки используют `secure_filename`?
- [`converter_routes.py`](src/routes/converter_routes.py) — проверить на path traversal

**Сложность:** 🟢 Низкая (0.5 дня)

### Итого Фаза 4: **~1.5 дня**

---

## 🎨 Фаза 5 — UI/UX (3-5 дней)

### 5.1 Drag & Drop для загрузки файлов

**Где:** [`templates/index.html`](templates/index.html) — область загрузки в конструкторе.

**Что сделать:**
```javascript
const dropZone = document.getElementById('constructorFileInput');
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#007bff';
});
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    // обработать как обычный file input
});
```

**UI:** Пунктирная область с текстом "📥 Перетащите файл сюда или нажмите для выбора".

**Сложность:** 🟢 Низкая (0.5 дня)

### 5.2 (Уже в Фазе 0) Тёмная тема, горячие клавиши, CSV-экспорт

### Итого Фаза 5: **~3 дня** (включая Фазу 0)

---

## 📊 Фаза 6 — Мониторинг и отладка (2-3 дня)

### 6.1 Prometheus метрики

**Зависимость:** `prometheus-flask-exporter>=0.23`

**Изменения** в [`app.py`](app.py):
```python
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app)
# По умолчанию добавляет:
# - flask_http_request_total (счётчик запросов)
# - flask_http_request_duration_seconds (гистограмма времени ответа)
# - requests_processing_seconds (время обработки)

# Кастомные метрики
metrics.register_default(
    metrics.counter(
        'constructor_pivot_builds_total',
        'Total pivot table builds',
        labels={'status': lambda: request.args.get('status', 'unknown')}
    )
)
```

**Endpoint:** `GET /metrics` — автоматически.

### 6.2 Дашборд администратора

**Новый файл:** `src/routes/admin_routes.py`

**Что показывает:**
- Список активных `_temp_files` (количество, общий размер)
- Количество активных сессий (файлы в `flask_session/`)
- Статус Celery-воркера (если Фаза 2 реализована)
- Количество задач в очереди
- Кнопка "🧹 Очистить кэш" — удалить все `_temp_files`
- Кнопка "🗑️ Очистить uploads" — удалить все временные файлы

**Защита:** Только для авторизованных админов (или по отдельному ключу).

**Фронтенд:** Новый раздел в сайдбаре "⚙️ Админ" (только если включено).

**Сложность:** 🟡 Средняя (1.5 дня)

### Итого Фаза 6: **~2.5 дня**

---

## 📊 Итоговая смета

| Фаза | Описание | Дней | Приоритет |
|------|----------|------|-----------|
| 0 | Быстрые победы (CSV, тёмная тема, хоткеи) | 1.5 | 🔴 Высокий |
| 1 | Тесты + Docker + линтеры | 4 | 🔴 Высокий |
| 2 | Производительность (Celery + пагинация) | 6 | 🟠 Средний |
| 3 | Новый функционал (формулы, PDF, версии, CSV, облака) | 8 | 🟡 Низкий |
| 4 | Безопасность (CSRF) | 1.5 | 🔴 Высокий |
| 5 | UI/UX (Drag&Drop) | 3 | 🟡 Низкий |
| 6 | Мониторинг (Prometheus + админка) | 2.5 | 🟡 Низкий |
| **ИТОГО** | **Всё вместе** | **~27 дней** | |

---

## 🎯 Рекомендуемый порядок (Roadmap)

### Sprint 1 — Фундамент (5 дней)
1. **Фаза 0** (1.5 дня) — быстрые победы для морального буста
2. **Фаза 1** (тесты, Docker) начать параллельно (2-3 дня)
3. **Фаза 4** (CSRF) — 1 день

### Sprint 2 — Производительность (6 дней)
4. **Фаза 2** (Celery + пагинация + WebSocket) — полный спринт

### Sprint 3 — Фичи (8 дней)
5. **Фаза 3** (вычисляемые поля, PDF, версионирование, CSV)

### Sprint 4 — Полировка (4 дня)
6. **Фаза 5** (Drag&Drop, тёмная тема доделки)
7. **Фаза 6** (мониторинг, админка)

---

## ⚠️ Риски и компромиссы

| Риск | Вероятность | Смягчение |
|------|-------------|-----------|
| Celery избыточен для текущих нагрузок | 🟡 Средняя | Использовать `threading` или APScheduler как лёгкую альтернативу |
| OAuth для облачных дисков (Яндекс/Google) | 🟠 Высокая | Ограничиться download-by-link (ссылка на файл), без полноценного OAuth |
| PDF с графиками — высокое потребление памяти | 🟡 Средняя | Ограничить размер данных для графика (топ-10 строк) |
| Вычисляемые поля — риск инъекций | 🟠 Высокая | Только `pd.eval()` без `eval`/`exec`, белый список функций |
| Поддержка CSV может сломать существующую логику | 🟢 Низкая | Отдельный путь для CSV, не затрагивающий Excel |

---

## 💬 Итоговая оценка выполнимости

### Общий вердикт: **ВЫПОЛНИМО на 95%**

**Почему не 100%:**
1. **OAuth для облачных дисков** — самая сложная часть. Требует регистрации приложения в Яндекс.Диск и Google Cloud Console, настройки redirect URI. Если сервер работает на localhost без публичного URL — OAuth не сработает (нужен ngrok или VPS). **Рекомендация:** отложить или сделать download-by-link.
2. **Celery + Redis** — мощно, но возможно избыточно. Если файлы < 50 МБ, синхронная обработка с индикацией загрузки (spinner) достаточна. Celery оправдан при файлах 100+ МБ или частых параллельных запросах.
3. **PDF с графиками** — качественная генерация отчётов через WeasyPrint/ReportLab трудоёмка. Matplotlib + PIL — проще, но менее гибко.

**Что можно сделать за 1 неделю (реалистично):**

| Что | Дней |
|-----|------|
| ✅ Автотесты (pytest) — constructor + API | 2 |
| ✅ Docker + docker-compose | 1 |
| ✅ CSV-экспорт + тёмная тема + хоткеи | 1 |
| ✅ CSRF-защита (Flask-WTF) | 1 |
| ✅ Drag&Drop + пагинация | 1 |
| ✅ Поддержка CSV-файлов | 1 |
| **Итого** | **7 дней** |

**Что можно сделать за 2 недели (оптимально):**
+ Версионирование сценариев (1 день)
+ Prometheus метрики + админка (2 дня)
+ Вычисляемые поля (2 дня)

**Что требует больше времени:**
- Celery + WebSocket (3-4 дня)
- PDF с графиками (2-3 дня)
- Облачные интеграции (3-4 дня)

---

> **Вывод:** Проект уже очень сильный. Предложенные улучшения превратят его из отличного инструмента для одного пользователя в production-ready систему, которую можно разворачивать в компании и подключать к CI/CD. Начинать рекомендую с **тестов и Docker** — это даст уверенность, что следующие изменения ничего не сломают.
