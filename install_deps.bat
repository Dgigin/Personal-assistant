@echo off
chcp 65001 > nul
title Excel Converter - Установка зависимостей
echo ============================================
echo   Установка зависимостей Python
echo ============================================
echo.

:: Переходим в директорию скрипта
cd /d "%~dp0"

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден!
    echo.
    echo Пожалуйста, установите Python 3.8+ с https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Создаём .env из .env.example, если его нет
if not exist "%~dp0.env" (
    echo [*] Создание .env из .env.example...
    copy "%~dp0.env.example" "%~dp0.env" > nul
    echo [OK] .env создан с гостевыми данными (guest/guest)
)

:: Обновляем pip
echo [*] Обновление pip...
python -m pip install --upgrade pip

:: Устанавливаем зависимости
echo.
echo [*] Установка зависимостей из requirements.txt...
echo.

pip install --user -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo [ERROR] Ошибка установки зависимостей.
    echo.
    echo Попробуйте установить вручную: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo [OK] Все зависимости успешно установлены!
echo.
echo Для запуска приложения: run.bat
echo Или: python app.py
echo.
pause
