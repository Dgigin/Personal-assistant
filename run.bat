@echo off
chcp 65001 > nul
title Personal Assistant
echo ============================================
echo   Personal Assistant - Запуск приложения
echo ============================================
echo.

:: Переходим в директорию скрипта
cd /d "%~dp0"

:: Удаляем мусор от предыдущих неудачных обновлений
if exist "%~dp0update.bat" del "%~dp0update.bat" >nul 2>&1
if exist "%~dp0apply_update.py" del "%~dp0apply_update.py" >nul 2>&1
if exist "%~dp0update_pending.flag" del "%~dp0update_pending.flag" >nul 2>&1

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
