@echo off
chcp 65001 >nul
title LISA FOREX - Launcher

:: Set working directory to where this bat file is located
cd /d "%~dp0\.."

echo ============================================================
echo    LISA FOREX - AUTO LAUNCHER
echo ============================================================
echo.

:: Step 1: Git pull latest code
echo [1/4] Updating code from GitHub...
git pull
echo.

:: Step 2: Start server.py (FastAPI + WebSocket + Chart)
echo [2/4] Starting server.py on port 8000...
start /B python -X utf8 server.py >nul 2>&1

:: Wait for server to start
timeout /t 3 /nobreak >nul

:: Step 3: Open chart and display in browser
echo [3/4] Opening browser...
start "" "http://localhost:8000/"
start "" "%~dp0display.html"

:: Step 4: Start Telegram Bot (foreground - keeps window open)
echo [4/4] Starting Telegram Bot...
echo.
echo ============================================================
echo  Press Ctrl+C to stop the bot and all services
echo ============================================================
echo.
cd /d "%~dp0"
python -X utf8 telegram_html_bot.py

:: When bot stops, clean up
echo.
echo Shutting down services...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
pause
