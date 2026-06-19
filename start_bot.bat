@echo off
echo ========================================
echo Multi-Exchange Trading Bot
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo [2/3] Starting trading bot with dashboard...
echo.
echo Dashboard will be available at:
echo    http://127.0.0.1:5000
echo.
echo Use the dashboard to:
echo  - Start/Stop trading bots
echo  - Monitor positions and balance
echo  - View trading statistics
echo  - Manage multiple accounts
echo.
echo ========================================
echo.

python -m src.main

pause
