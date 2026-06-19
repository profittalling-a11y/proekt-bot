@echo off
echo ========================================
echo Testing TradingView Webhook (SSL Fixed)
echo ========================================
echo.
echo Enter your ngrok URL (without https://):
set /p NGROK_URL="ngrok URL: "
echo.
echo [Step 1] Opening browser to activate ngrok...
start https://%NGROK_URL%/tradingview/webhook
echo.
echo Press any key AFTER you clicked "Visit Site" in browser...
pause
echo.
echo [Step 2] Sending TEST BUY signal for BTCUSDT...
echo.

curl -k -X POST https://%NGROK_URL%/tradingview/webhook -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSDT\",\"action\":\"buy\",\"price\":65000,\"stop_loss\":64000}"

echo.
echo.
echo Check your webhook server logs for the result!
echo.
pause
