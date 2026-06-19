# TradingView Webhook Integration

## Как это работает

1. **TradingView** - вы настраиваете индикаторы и алерты на графике
2. **Webhook** - TradingView отправляет HTTP запрос на ваш сервер при срабатывании алерта
3. **Бот** - получает сигнал и автоматически открывает/закрывает позицию через OKX API
4. **Risk Manager** - контролирует стоп-лоссы и управление капиталом

---

## Шаг 1: Настройка бота

### 1.1 Добавьте в `.env` файл:

```bash
# TradingView Webhook Settings
TRADINGVIEW_WEBHOOK_SECRET=ваш_секретный_ключ_12345
WEBHOOK_PORT=5001
```

### 1.2 Запустите бота с вебхуком:

```bash
cd "C:\Users\desin\OneDrive\Рабочий стол\Proekt Bot"
venv/Scripts/python.exe -m src.main_webhook
```

---

## Шаг 2: Публичный доступ (ngrok)

Чтобы TradingView мог отправлять вебхуки на ваш компьютер, нужен публичный URL.

### 2.1 Установите ngrok:

1. Скачайте: https://ngrok.com/download
2. Распакуйте в удобную папку
3. Зарегистрируйтесь на ngrok.com и получите токен

### 2.2 Запустите ngrok:

```bash
ngrok http 5001
```

Вы получите URL типа: `https://abc123.ngrok.io`

**ВАЖНО:** Оставьте ngrok запущенным все время работы!

---

## Шаг 3: Настройка TradingView

### 3.1 Создайте алерт на графике

1. Откройте график нужной пары (например, BTCUSDT)
2. Добавьте индикатор Supertrend (или любой другой)
3. Нажмите **Alert** (будильник) справа вверху
4. Настройте условия:
   - **Condition:** Supertrend (или ваш индикатор)
   - **Crossing Up** = BUY сигнал
   - **Crossing Down** = SELL сигнал

### 3.2 Настройте Webhook

В окне создания алерта:

**Webhook URL:**
```
https://ваш-ngrok-url.ngrok.io/tradingview/webhook
```

**Message (для BUY):**
```json
{
  "symbol": "BTCUSDT",
  "action": "buy",
  "price": {{close}},
  "stop_loss": {{low}},
  "take_profit": null
}
```

**Message (для SELL):**
```json
{
  "symbol": "BTCUSDT",
  "action": "sell",
  "price": {{close}},
  "stop_loss": {{high}},
  "take_profit": null
}
```

**Message (для CLOSE):**
```json
{
  "symbol": "BTCUSDT",
  "action": "close",
  "price": {{close}}
}
```

### 3.3 Переменные TradingView

TradingView подставит реальные значения:
- `{{close}}` - цена закрытия свечи
- `{{high}}` - максимум свечи
- `{{low}}` - минимум свечи
- `{{open}}` - цена открытия
- `{{volume}}` - объем

---

## Шаг 4: Примеры настройки алертов

### Пример 1: Supertrend Buy/Sell

**Condition:**
- Indicator: Supertrend
- When: Crossing Up (для BUY) или Crossing Down (для SELL)

**Webhook Message (BUY):**
```json
{
  "symbol": "BTCUSDT",
  "action": "buy",
  "price": {{close}},
  "stop_loss": {{low}}
}
```

### Пример 2: EMA Crossover

**Condition:**
- EMA(9) crossing EMA(21)

**Webhook Message:**
```json
{
  "symbol": "ETHUSDT",
  "action": "buy",
  "price": {{close}},
  "stop_loss": null
}
```

### Пример 3: Закрытие позиции по индикатору

**Condition:**
- RSI > 70 (перекупленность)

**Webhook Message:**
```json
{
  "symbol": "BTCUSDT",
  "action": "close",
  "price": {{close}}
}
```

---

## Шаг 5: Тестирование

### 5.1 Ручная отправка вебхука (для теста)

Используйте Postman или curl:

```bash
curl -X POST https://ваш-ngrok-url.ngrok.io/tradingview/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "action": "buy",
    "price": 50000,
    "stop_loss": 49000
  }'
```

### 5.2 Проверьте логи

В логах бота должно появиться:
```
TradingView webhook: BUY BTCUSDT @ 50000
Opening LONG: qty=0.0020, entry=50000.00, SL=49000.00
LONG position opened: BTCUSDT
```

---

## Управление рисками

Бот автоматически:

1. **Рассчитывает размер позиции** на основе:
   - Баланса счета
   - Расстояния до стоп-лосса
   - Настроек риска (2% по умолчанию)

2. **Устанавливает стоп-лосс**:
   - Из вебхука (если указан)
   - Или автоматически 2% от входа

3. **Контролирует лимиты**:
   - Максимальное количество позиций
   - Дневной лимит убытка
   - Минимальный баланс

---

## Форматы символов

Бот автоматически преобразует:

**TradingView → OKX:**
- `BTCUSDT` → `BTC-USDT-SWAP`
- `ETHUSDT` → `ETH-USDT-SWAP`

**TradingView → Bybit:**
- `BTCUSDT` → `BTCUSDT` (без изменений)

---

## Безопасность

### Защита вебхука

В `.env` установите секретный ключ:
```bash
TRADINGVIEW_WEBHOOK_SECRET=сложный_случайный_ключ_12345
```

Бот будет проверять подпись запроса.

### Настройка TradingView (Pro план)

Если у вас Pro план TradingView, добавьте в Headers:
```
X-Signature: [будет рассчитываться автоматически]
```

---

## Troubleshooting

### Проблема: Вебхук не приходит

**Решение:**
1. Проверьте что ngrok запущен
2. Проверьте URL в TradingView (должен быть `https://...ngrok.io/tradingview/webhook`)
3. Проверьте логи ngrok: `http://127.0.0.1:4040`

### Проблема: Сделка не открывается

**Решение:**
1. Проверьте логи бота: `tail -f logs/trading_bot.log`
2. Проверьте баланс счета
3. Проверьте что символ правильный (BTCUSDT, не BTC/USDT)

### Проблема: Ошибка "Invalid signature"

**Решение:**
1. Убедитесь что `TRADINGVIEW_WEBHOOK_SECRET` одинаковый в `.env` и TradingView
2. Или удалите `TRADINGVIEW_WEBHOOK_SECRET` из `.env` (отключит проверку)

---

## Преимущества TradingView интеграции

✅ **Не нужно программировать индикаторы** - используйте любые индикаторы TradingView  
✅ **Визуальный контроль** - видите сигналы на графике  
✅ **Гибкость** - можете менять стратегию без изменения кода  
✅ **Надежность** - TradingView работает 24/7  
✅ **Множество индикаторов** - тысячи готовых индикаторов в библиотеке  

---

## Примеры стратегий

### 1. Простой Supertrend

```
Алерт 1 (BUY): Supertrend crossing up
Алерт 2 (SELL): Supertrend crossing down
```

### 2. EMA + RSI

```
Алерт 1 (BUY): EMA(9) > EMA(21) AND RSI < 30
Алерт 2 (SELL): EMA(9) < EMA(21) AND RSI > 70
```

### 3. Breakout стратегия

```
Алерт 1 (BUY): Close > Highest(High, 20)
Алерт 2 (CLOSE): Close < SMA(20)
```

---

## Следующие шаги

1. ✅ Создайте `.env` файл с настройками
2. ✅ Запустите бота с вебхуком
3. ✅ Запустите ngrok для публичного доступа
4. ✅ Настройте алерты в TradingView
5. ✅ Протестируйте на малых суммах
6. ✅ Масштабируйте после успешных тестов

**Успешной торговли! 🚀**
