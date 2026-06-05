# Проект `personal_assistant` — Документация

> **Дата последнего обновления:** 2026-06-04
> **Текущая версия:** 1.0.7
> **Репозиторий:** [Dgigin/Personal-assistant](https://github.com/Dgigin/Personal-assistant)

---

## 📋 Структура документации

Документация проекта разбита на категорийные файлы:

| Файл | Описание | Статус |
|------|----------|--------|
| [`architecture.md`](architecture.md) | Архитектура проекта, структура директорий, технологический стек, API-эндпоинты | ✅ Актуально |
| [`security.md`](security.md) | Аудит безопасности (16 проблем), детальный аудит архитектуры (15 проблем), рекомендации | ✅ Актуально |
| [`features.md`](features.md) | Полный функционал: Конвертер, Конструктор, CSV, DeepSeek, EasyOCR, задачи, автообновление, установщик, баг-фиксы | ✅ Актуально |
| [`roadmap.md`](roadmap.md) | Дорожная карта: выполненные фазы, план улучшений (Фазы 0-6), смета, риски | ✅ Актуально |

---

## 🗺️ Навигация

### Для понимания структуры проекта
→ [**Архитектура**](architecture.md) — файловая структура, компоненты, API, технологии

### Для оценки безопасности
→ [**Безопасность**](security.md) — аудит, найденные проблемы, статус исправления, рекомендации

### Для изучения возможностей
→ [**Функционал**](features.md) — все модули, фичи, баг-фиксы, история версий

### Для планирования разработки
→ [**Roadmap**](roadmap.md) — выполненные работы, план улучшений, смета, спринты, риски

---

## 🏷️ История версий

| Версия | Дата | Ссылка | Основные изменения |
|--------|------|--------|-------------------|
| v1.0.8 | 05.06.2026 | — | SQLite-кэш данных листа, фильтрация колонок, UI relocation кнопки загрузки |
| v1.0.7 | 04.06.2026 | [Релиз](https://github.com/Dgigin/Personal-assistant/releases/tag/v1.0.7) | CSV поддержка, оптимизация загрузки .xlsx, индикаторы прогресса |
| v1.0.6 | 04.06.2026 | [Релиз](https://github.com/Dgigin/Personal-assistant/releases/tag/v1.0.6) | Исправление update.bat (полная переработка) |
| v1.0.5 | 04.06.2026 | [Релиз](https://github.com/Dgigin/Personal-assistant/releases/tag/v1.0.5) | Очистка stale файлов, подавление логов Werkzeug |
| v1.0.4 | 04.06.2026 | [Релиз](https://github.com/Dgigin/Personal-assistant/releases/tag/v1.0.4) | Автообновление, установщик, безопасность |
| v1.0.3 | 03.06.2026 | — | Конструктор v2, баг-фиксы |
| v1.0.2 | 02.06.2026 | — | Конструктор v1, аудит архитектуры |
| v1.0.1 | 01.06.2026 | — | EasyOCR, DeepSeek чат |
| v1.0.0 | 30.05.2026 | — | Первый релиз |

---

## ⚡ Быстрый старт

```bash
# Запуск в режиме разработки
python app.py

# Запуск в production (Waitress)
python -m waitress --host=127.0.0.1 --port=5000 wsgi:application
```

**Требования:** Python 3.x, зависимости из `requirements.txt`

---

## 📁 Изменённые файлы (v1.0.7)

| Файл | Изменения |
|------|-----------|
| [`version.json`](../version.json) | Версия обновлена до 1.0.7 |
| [`src/utils/file_utils.py`](../src/utils/file_utils.py) | Добавлена `read_file_to_df()` — централизованная функция чтения CSV и Excel |
| [`src/services/constructor.py`](../src/services/constructor.py) | Замена всех `pd.read_excel()` на `read_file_to_df()`, оптимизация `load_sheet_data()` (nrows), поддержка CSV |
| [`src/services/converter.py`](../src/services/converter.py) | Замена `pd.read_excel()` на `read_file_to_df()` |
| [`src/routes/constructor_routes.py`](../src/routes/constructor_routes.py) | Добавлено расширение `.csv` в разрешённые |
| [`src/routes/converter_routes.py`](../src/routes/converter_routes.py) | Импорт `read_file_to_df()`, динамическое определение расширения |
| [`templates/index.html`](../templates/index.html) | accept-атрибуты `.xlsx, .xls, .csv`, CSS-спиннеры, блокировка кнопок |
| [`plans/architecture.md`](architecture.md) | 🆕 Создан |
| [`plans/security.md`](security.md) | 🆕 Создан |
| [`plans/features.md`](features.md) | 🆕 Создан |
| [`plans/roadmap.md`](roadmap.md) | 🆕 Создан |

## 🆕 Изменённые файлы (v1.0.8)

| Файл | Изменения |
|------|-----------|
| [`src/utils/sqlite_cache.py`](../src/utils/sqlite_cache.py) | 🆕 Создан — модуль SQLite-кэша: create/save/query/load/delete |
| [`src/routes/constructor_routes.py`](../src/routes/constructor_routes.py) | `load_sheet()` — чтение Excel ОДИН раз → SQLite + preview; `close_file()` — очистка кэша; `pivot_table()` — загрузка из SQLite если нет `cached_df`; `preview_data()` — запрос через SQLite-кэш |
| [`src/services/constructor.py`](../src/services/constructor.py) | `build_pivot_table()` — добавлен параметр `selected_columns`, фильтрация колонок с сохранением pivot-обязательных |
| [`templates/index.html`](../templates/index.html) | Кнопка загрузки листа и прогресс-бар перенесены под селект листа; сбор `selected_columns` из чекбоксов |
| [`version.json`](../version.json) | Версия обновлена до 1.0.8 |
| [`plans/features.md`](features.md) | Добавлены секции: фильтрация колонок, SQLite-кэш, UI relocation |
| [`plans/roadmap.md`](roadmap.md) | Добавлена Фаза 2.7 (SQLite + column filtering + UI) |
| [`plans/architecture.md`](architecture.md) | Добавлен `sqlite_cache.py`, папка `sqlite_cache/`, обновлена секция БД |
| [`plans/improvements_plan_new.md`](improvements_plan_new.md) | Добавлена v1.0.8 в историю и список изменённых файлов |
