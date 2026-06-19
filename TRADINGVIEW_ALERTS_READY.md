# 🚀 ГОТОВЫЕ НАСТРОЙКИ АЛЕРТОВ ДЛЯ TRADINGVIEW

## ⚡ ВАЖНО: Сначала получите ваш ngrok URL

1. Откройте терминал и выполните:
```bash
ngrok http 5001
```

2. Скопируйте URL из строки `Forwarding`, например: `https://abc123.ngrok.io`

3. **ЗАМЕНИТЕ** в настройках ниже `ВАШ_NGROK_URL` на ваш реальный URL

---

## 📊 ИНДИКАТОР: Supertrend (10, 3.0)

### Настройки индикатора:
- **ATR Length:** 10
- **Factor:** 3.0
- **Timeframe:** 15 минут (или ваш выбор)

---

## 🟢 АЛЕРТ 1: BUY SIGNAL (Открытие LONG)

### Шаг 1: Создание алерта
1. На графике TradingView нажмите кнопку **⏰ Alert** (справа вверху)
2. Заполните следующие поля:

### Поля алерта:

**Condition (Условие):**
```
Supertrend
Crossing Up
Value
```
Или выберите из выпадающего списка:
- Indicator: `Supertrend`
- Event: `Crossing Up` или `Value Increasing`

**Options:**
- ✅ Once Per Bar Close (галочка)
- Expiration: `Open-ended`

**Alert name:**
```
BTC-USDT LONG Entry (Supertrend Buy)
```

**Alert actions:**
- ✅ **Webhook URL** (обязательно включите!)

**Webhook URL:**
```
https://ВАШ_NGROK_URL.ngrok.io/tradingview/webhook
```
⚠️ **ЗАМЕНИТЕ ВАШ_NGROK_URL на ваш реальный ngrok URL!**

Например: `https://abc123.ngrok.io/tradingview/webhook`

**Message:**
```json
{
  "symbol": "{{ticker}}",
  "action": "buy",
  "price": {{close}},
  "stop_loss": {{low}},
  "take_profit": null
}
```

⚠️ **ВАЖНО:** Скопируйте message ТОЧНО как здесь, включая `{{ticker}}`, `{{close}}`, `{{low}}`

### Шаг 2: Нажмите **Create**

---

## 🔴 АЛЕРТ 2: SELL SIGNAL (Открытие SHORT)

### Шаг 1: Создание алерта
1. Снова нажмите **⏰ Alert**
2. Заполните следующие поля:

### Поля алерта:

**Condition (Условие):**
```
Supertrend
Crossing Down
Value
```
Или:
- Indicator: `Supertrend`
- Event: `Crossing Down` или `Value Decreasing`

**Options:**
- ✅ Once Per Bar Close (галочка)
- Expiration: `Open-ended`

**Alert name:**
```
BTC-USDT SHORT Entry (Supertrend Sell)
```

**Alert actions:**
- ✅ **Webhook URL** (обязательно включите!)

**Webhook URL:**
```
https://ВАШ_NGROK_URL.ngrok.io/tradingview/webhook
```
⚠️ **ЗАМЕНИТЕ ВАШ_NGROK_URL на ваш реальный ngrok URL!**

**Message:**
```json
{
  "symbol": "{{ticker}}",
  "action": "sell",
  "price": {{close}},
  "stop_loss": {{high}},
  "take_profit": null
}
```

### Шаг 2: Нажмите **Create**

---

## 🔵 АЛЕРТ 3: CLOSE POSITION (Закрытие позиции при смене тренда)

### Опционально, но рекомендуется!

### Шаг 1: Создание алерта
1. Нажмите **⏰ Alert**
2. Заполните:

**Condition (Условие):**
```
Supertrend
Any alert() function call
```
Или просто:
- `Crossing` (любое пересечение)

**Alert name:**
```
BTC-USDT Close Position (Trend Change)
```

**Webhook URL:**
```
https://ВАШ_NGROK_URL.ngrok.io/tradingview/webhook
```

**Message:**
```json
{
  "symbol": "{{ticker}}",
  "action": "close",
  "price": {{close}}
}
```

---

## 📋 ЧЕКЛИСТ ПРОВЕРКИ

Перед тестированием проверьте:

- [ ] Webhook сервер запущен (`start_webhook.bat`)
- [ ] Ngrok запущен (`ngrok http 5001`)
- [ ] Скопировали ngrok URL в настройки алертов
- [ ] В `.env` файле указаны API ключи OKX
- [ ] В `.env` указан `TRADING_MODE=testnet` (для тестирования)
- [ ] Создали алерт для BUY (Crossing Up)
- [ ] Создали алерт для SELL (Crossing Down)
- [ ] В Message скопировали JSON точно как в инструкции

---

## 🧪 ТЕСТИРОВАНИЕ

### Вариант 1: Ручной тест (до первого реального сигнала)

Откройте новый терминал и выполните:

**Тест BUY сигнала:**
```bash
curl -X POST https://ВАШ_NGROK_URL.ngrok.io/tradingview/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"BTCUSDT\",\"action\":\"buy\",\"price\":65000,\"stop_loss\":64000}"
```

**Тест SELL сигнала:**
```bash
curl -X POST https://ВАШ_NGROK_URL.ngrok.io/tradingview/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"BTCUSDT\",\"action\":\"sell\",\"price\":65000,\"stop_loss\":66000}"
```

**Тест закрытия:**
```bash
curl -X POST https://ВАШ_NGROK_URL.ngrok.io/tradingview/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"BTCUSDT\",\"action\":\"close\",\"price\":65000}"
```

### Вариант 2: Проверка в логах

Смотрите в окно где запущен `start_webhook.bat`:

**Успешный BUY:**
```
TradingView webhook: BUY BTCUSDT @ 65000.00
Balance: 100.00 USDT
Opening LONG: qty=0.0015, entry=65000.00, SL=64000.00
LONG position opened: BTC-USDT-SWAP
```

**Успешный SELL:**
```
TradingView webhook: SELL BTCUSDT @ 65000.00
Opening SHORT: qty=0.0015, entry=65000.00, SL=66000.00
SHORT position opened: BTC-USDT-SWAP
```

---

## 🌟 ГОТОВЫЕ НАСТРОЙКИ ДЛЯ РАЗНЫХ ПАР

### Bitcoin (BTCUSDT)

**BUY Message:**
```json
{"symbol":"BTCUSDT","action":"buy","price":{{close}},"stop_loss":{{low}}}
```

**SELL Message:**
```json
{"symbol":"BTCUSDT","action":"sell","price":{{close}},"stop_loss":{{high}}}
```

### Ethereum (ETHUSDT)

**BUY Message:**
```json
{"symbol":"ETHUSDT","action":"buy","price":{{close}},"stop_loss":{{low}}}
```

**SELL Message:**
```json
{"symbol":"ETHUSDT","action":"sell","price":{{close}},"stop_loss":{{high}}}
```

### Solana (SOLUSDT)

**BUY Message:**
```json
{"symbol":"SOLUSDT","action":"buy","price":{{close}},"stop_loss":{{low}}}
```

**SELL Message:**
```json
{"symbol":"SOLUSDT","action":"sell","price":{{close}},"stop_loss":{{high}}}
```

---

## 📱 МОНИТОРИНГ

### Где смотреть результаты:

1. **Логи вебхук-сервера** - в терминале где запущен `start_webhook.bat`
2. **Логи в файле** - `logs/webhook.log`
3. **Telegram** - если настроили, придут уведомления
4. **OKX аккаунт** - проверьте открытые позиции

### Команда для просмотра последних логов:
```bash
tail -50 logs/webhook.log
```

---

## ⚠️ ВАЖНЫЕ МОМЕНТЫ

### 1. Формат символа
- В TradingView: `BTCUSDT`, `ETHUSDT`
- Бот преобразует в: `BTC-USDT-SWAP`, `ETH-USDT-SWAP` (для OKX)

### 2. Стоп-лосс
- `{{low}}` для LONG - минимум текущей свечи
- `{{high}}` для SHORT - максимум текущей свечи
- Можно указать конкретное значение: `"stop_loss": 64000`

### 3. Тайм-фрейм
Индикатор Supertrend работает на любом таймфрейме:
- **5m** - много сигналов, высокая частота
- **15m** - оптимально для начала
- **1H** - меньше сигналов, но надежнее

### 4. Риск-менеджмент
Бот автоматически:
- Рассчитывает размер позиции от баланса
- Не откроет позицию если недостаточно средств
- Не откроет больше 10 позиций одновременно
- Остановит торговлю при -20% дневного убытка

---

## 🎯 ИТОГО: ЧТО НУЖНО СДЕЛАТЬ

### 1️⃣ В терминале 1:
```bash
cd "C:\Users\desin\OneDrive\Рабочий стол\Proekt Bot"
start_webhook.bat
```

### 2️⃣ В терминале 2:
```bash
ngrok http 5001
```
Скопируйте URL (например: `https://abc123.ngrok.io`)

### 3️⃣ В TradingView:
1. Откройте график BTCUSDT
2. Добавьте индикатор Supertrend (10, 3.0)
3. Создайте алерт для BUY (скопируйте настройки выше)
4. Создайте алерт для SELL (скопируйте настройки выше)

### 4️⃣ Проверьте:
```bash
curl -X POST https://ваш-ngrok-url.ngrok.io/tradingview/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"BTCUSDT\",\"action\":\"buy\",\"price\":65000,\"stop_loss\":64000}"
```

**Если в логах появилось "Opening LONG" - ВСЕ РАБОТАЕТ!** ✅

---

## 📞 Помощь

Если что-то не работает, проверьте:
1. Webhook сервер работает (должен быть запущен)
2. Ngrok показывает `online` статус
3. URL в TradingView правильный (с `/tradingview/webhook` в конце)
4. В Message JSON правильно скопирован

**Готово! Теперь бот будет автоматически торговать по сигналам Supertrend!** 🚀
