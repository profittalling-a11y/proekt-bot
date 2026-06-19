# 🚀 Быстрый старт TradingView интеграции

## За 5 минут до первой сделки

### Шаг 1: Настройте .env файл

Скопируйте `.env.tradingview` в `.env` и заполните:

```bash
# Обязательные поля
OKX_API_KEY=ваш_ключ
OKX_API_SECRET=ваш_секрет
OKX_PASSPHRASE=ваш_пароль

# Опционально (для безопасности)
TRADINGVIEW_WEBHOOK_SECRET=любая_случайная_строка_12345
```

### Шаг 2: Запустите вебхук-сервер

**Вариант A - через bat файл:**
```bash
start_webhook.bat
```

**Вариант B - через командную строку:**
```bash
cd "C:\Users\desin\OneDrive\Рабочий стол\Proekt Bot"
venv\Scripts\activate
python -m src.main_webhook
```

Вы увидите:
```
TRADINGVIEW WEBHOOK SERVER STARTING
Webhook URL: http://0.0.0.0:5001/tradingview/webhook
📡 Waiting for TradingView webhooks...
```

### Шаг 3: Запустите ngrok (в НОВОМ окне терминала)

```bash
ngrok http 5001
```

Скопируйте URL из вывода ngrok (например: `https://abc123.ngrok.io`)

### Шаг 4: Настройте алерт в TradingView

1. Откройте график (например, BTCUSDT)
2. Добавьте индикатор (например, Supertrend)
3. Создайте Alert (кнопка будильника)
4. В поле **Webhook URL** вставьте:
   ```
   https://abc123.ngrok.io/tradingview/webhook
   ```

5. В поле **Message** вставьте:

**Для сигнала BUY:**
```json
{
  "symbol": "BTCUSDT",
  "action": "buy",
  "price": {{close}},
  "stop_loss": {{low}}
}
```

**Для сигнала SELL:**
```json
{
  "symbol": "BTCUSDT",
  "action": "sell",
  "price": {{close}},
  "stop_loss": {{high}}
}
```

**Для закрытия позиции:**
```json
{
  "symbol": "BTCUSDT",
  "action": "close",
  "price": {{close}}
}
```

6. Нажмите **Create**

### Шаг 5: Протестируйте

Отправьте тестовый вебхук:

```bash
curl -X POST https://ваш-ngrok-url.ngrok.io/tradingview/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","action":"buy","price":50000,"stop_loss":49000}'
```

В логах должно появиться:
```
TradingView webhook: BUY BTCUSDT @ 50000
Opening LONG: qty=0.0020, entry=50000.00, SL=49000.00
```

---

## ✅ Готово!

Теперь при срабатывании алерта в TradingView, бот автоматически:
- ✅ Получит сигнал
- ✅ Рассчитает размер позиции
- ✅ Откроет сделку через OKX API
- ✅ Установит стоп-лосс
- ✅ Отправит уведомление в Telegram

---

## 📊 Примеры стратегий

### Supertrend (самый простой)

**Alert условие:**
- Indicator: Supertrend
- Crossing Up → BUY
- Crossing Down → SELL

**Message для BUY:**
```json
{"symbol":"{{ticker}}","action":"buy","price":{{close}},"stop_loss":{{low}}}
```

### EMA Crossover

**Alert условие:**
- EMA(9) crossing above EMA(21) → BUY
- EMA(9) crossing below EMA(21) → SELL

**Message:**
```json
{"symbol":"{{ticker}}","action":"buy","price":{{close}},"stop_loss":null}
```

### RSI Overbought/Oversold

**Alert для закрытия:**
- RSI > 70 → CLOSE (для long позиций)
- RSI < 30 → CLOSE (для short позиций)

**Message:**
```json
{"symbol":"{{ticker}}","action":"close","price":{{close}}}
```

---

## 🛡️ Риск-менеджмент

Бот автоматически контролирует:

- **Размер позиции** - рассчитывается от баланса и стоп-лосса
- **Максимум позиций** - не более 10 одновременно (настраивается)
- **Дневной лимит** - максимум -20% в день
- **Стоп-лосс** - обязательно на каждую сделку

---

## ❓ Частые вопросы

**Q: Бот не открывает сделки**  
A: Проверьте логи: `tail -f logs/webhook.log`

**Q: Вебхук не приходит от TradingView**  
A: Проверьте что ngrok запущен и URL правильный

**Q: Ошибка "Invalid symbol"**  
A: Используйте формат BTCUSDT (без пробелов и слешей)

**Q: Можно ли использовать несколько пар?**  
A: Да! Создайте отдельный алерт для каждой пары

**Q: Нужен ли Pro план TradingView?**  
A: Нет, бесплатный план поддерживает вебхуки

---

## 📚 Полная документация

См. файл `TRADINGVIEW_SETUP.md` для детальной информации.

---

**Успешной торговли! 🎯**
