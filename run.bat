@echo off
chcp 65001 > nul
title Excel Converter
echo ============================================
echo   Excel Converter - Запуск приложения
echo ============================================
echo.

:: Переходим в директорию скрипта
cd /d "%~dp0"

:: Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден!
    echo.
    echo Пожалуйста, установите Python 3.8+ с https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Создаём .env из .env.example, если его нет (с уникальным SECRET_KEY)
if not exist "%~dp0.env" (
    python "%~dp0setup_env.py"
)

:: Проверяем зависимости
echo [*] Проверка зависимостей...
python -c "import flask" 2>nul
if errorlevel 1 (
    echo [*] Установка зависимостей...
    pip install --user -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Ошибка установки зависимостей.
        echo.
        echo Попробуйте запустить install_deps.bat от имени администратора.
        pause
        exit /b 1
    )
    echo [OK] Зависимости установлены.
)

echo.
echo [*] Запуск сервера...
echo.
echo Откройте в браузере: http://localhost:5000
echo Для остановки сервера закройте это окно или нажмите Ctrl+C
echo.
echo ============================================
echo.

python app.py

if errorlevel 1 (
    echo.
    echo [ERROR] Сервер завершился с ошибкой.
    pause
    exit /b 1
)

pause
