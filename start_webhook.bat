@echo off
echo ========================================
echo TradingView Webhook Server
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo [2/3] Starting webhook server...
echo.
echo Webhook URL will be: http://localhost:5001/tradingview/webhook
echo.
echo IMPORTANT: You need to run ngrok in another terminal:
echo    ngrok http 5001
echo.
echo Then use the ngrok URL in TradingView alerts!
echo.
echo ========================================

python -m src.main_webhook

pause
