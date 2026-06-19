@echo off
echo ========================================
echo Testing TradingView Webhook
echo ========================================
echo.
echo Enter your ngrok URL (without https://):
set /p NGROK_URL="ngrok URL: "
echo.
echo Sending TEST BUY signal for BTCUSDT...
echo.

curl -X POST https://%NGROK_URL%/tradingview/webhook -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSDT\",\"action\":\"buy\",\"price\":65000,\"stop_loss\":64000}"

echo.
echo.
echo Check your webhook server logs for the result!
echo.
pause
