@echo off
chcp 65001 >nul
title LISA FOREX - MT5 Version

:: Set working directory to where this bat file is located
cd /d "%~dp0"

echo ============================================================
echo    LISA FOREX - MT5 EXNESS VERSION (TEST)
echo ============================================================
echo.

:: Step 1: Check MT5 running
echo [1/3] Checking MT5...
echo       Dam bao MetaTrader 5 dang mo va da login EXNESS
echo.

:: Step 2: Start server(mt5).py
echo [2/3] Starting server(mt5).py on port 8000...
start /B python -X utf8 "server(mt5).py" >nul 2>&1

:: Wait for server to start
timeout /t 3 /nobreak >nul

echo       Server ready!
echo.
echo ------------------------------------------------------------
echo   LINKS (copy paste vao Chrome):
echo   http://localhost:8000/display
echo   http://localhost:8000
echo ------------------------------------------------------------
echo.

:: Step 3: Start Telegram Bot (foreground - keeps window open)
echo [3/3] Starting Telegram Bot (MT5)...
echo.
echo ============================================================
echo  Press Ctrl+C to stop the bot and all services
echo ============================================================
echo.
python -X utf8 "telegram_html_bot(mt5).py"

:: When bot stops, clean up
echo.
echo Shutting down services...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
pause
