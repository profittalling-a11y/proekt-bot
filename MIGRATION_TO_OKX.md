# Миграция с Bybit на OKX

## Что изменилось

Бот был полностью адаптирован для работы с биржей OKX вместо Bybit.

### Основные изменения

1. **API клиент**: `bybit_client.py` заменен на `okx_client.py`
2. **Конфигурация**: Обновлены параметры API и форматы символов
3. **Формат символов**: `BTCUSDT` → `BTC-USDT-SWAP` (для бессрочных фьючерсов)
4. **Таймфреймы**: `15` → `15m`, `60` → `1H`, `1440` → `1D`
5. **API ключи**: Теперь требуется passphrase в дополнение к key и secret

## Шаги для запуска

### 1. Установите зависимости

```bash
pip install -r requirements.txt
```

Основное изменение: `pybit` заменен на `okx`

### 2. Настройте .env файл

Обновите ваш `.env` файл с новыми параметрами:

```env
# OKX API Credentials
OKX_API_KEY=your_api_key_here
OKX_API_SECRET=your_api_secret_here
OKX_PASSPHRASE=your_passphrase_here

# Trading Mode: testnet, paper, live
TRADING_MODE=testnet

# Trading Parameters
AUTO_SCAN=true
MIN_VOLUME_24H=1000000
MAX_SYMBOLS=10

# Manual symbols (используйте формат OKX для SWAP)
SYMBOLS=BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP

TIMEFRAME=15
ATR_PERIOD=10
SUPERTREND_MULTIPLIER=3.0

# Risk Management
FIXED_POSITION_SIZE=1.0
RISK_PER_POSITION=2.0
MAX_POSITIONS=10

# Leverage (формат: SYMBOL:LEVERAGE)
LEVERAGE_CONFIG=BTC-USDT-SWAP:50,ETH-USDT-SWAP:50,SOL-USDT-SWAP:25

MAX_DAILY_LOSS=20.0
COOLDOWN_AFTER_LOSS=300
MIN_BALANCE=100.0

# Telegram
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

LOG_LEVEL=INFO
```

### 3. Получите API ключи OKX

1. Зайдите на [OKX](https://www.okx.com)
2. Перейдите в API Management
3. Создайте новый API ключ
4. **Важно**: Сохраните passphrase - он нужен для аутентификации
5. Установите права: Trade (для торговли), Read (для чтения данных)
6. Рекомендуется включить IP whitelist для безопасности

### 4. Демо-режим (testnet)

OKX использует единый URL для demo и live торговли. Режим определяется флагом в API запросах:
- `TRADING_MODE=testnet` - демо-торговля с виртуальными средствами
- `TRADING_MODE=live` - реальная торговля

Для демо-торговли:
1. Создайте demo аккаунт на OKX
2. Получите demo API ключи
3. Используйте их в `.env` с `TRADING_MODE=testnet`

### 5. Запустите бота

```bash
python -m src.main
```

## Ключевые отличия OKX от Bybit

### Формат символов

**Bybit**: `BTCUSDT`, `ETHUSDT`
**OKX**: `BTC-USDT-SWAP`, `ETH-USDT-SWAP`

Для бессрочных фьючерсов (perpetual) используется суффикс `-SWAP`

### Таймфреймы

**Bybit**: `1`, `5`, `15`, `60`, `240`, `D`
**OKX**: `1m`, `5m`, `15m`, `1H`, `4H`, `1D`

### API аутентификация

**Bybit**: API Key + API Secret
**OKX**: API Key + API Secret + Passphrase

### Размер позиции

**Bybit**: Размер в базовой валюте (BTC, ETH)
**OKX**: Размер в контрактах (1 контракт = 1 базовая валюта для SWAP)

### Leverage

**Bybit**: До 100x на большинстве пар
**OKX**: До 125x на некоторых парах (бот ограничивает до 50x для безопасности)

## Проверка работы

1. **Проверьте подключение**:
   - Бот должен успешно подключиться к OKX API
   - В логах должно быть: `OKX client initialized (demo=True)`

2. **Проверьте баланс**:
   - Бот должен показать ваш USDT баланс
   - Для demo аккаунта это будут виртуальные средства

3. **Проверьте получение данных**:
   - Бот должен получать свечи (klines)
   - Должны рассчитываться индикаторы

4. **Тестируйте на demo**:
   - Минимум 1 неделю тестирования на demo
   - Проверьте открытие/закрытие позиций
   - Проверьте stop loss и take profit

## Автоматическое сканирование рынка

Если `AUTO_SCAN=true`, бот автоматически найдет ликвидные пары на OKX:

```python
# Бот сканирует все SWAP пары
# Фильтрует по объему (MIN_VOLUME_24H)
# Выбирает топ MAX_SYMBOLS пар
# Автоматически определяет максимальное плечо
```

## Troubleshooting

### Ошибка аутентификации

```
OKX API Error 50113: Invalid sign
```

**Решение**: Проверьте правильность API key, secret и passphrase

### Ошибка формата символа

```
OKX API Error 51001: Instrument ID does not exist
```

**Решение**: Используйте формат `BTC-USDT-SWAP` вместо `BTCUSDT`

### Недостаточный баланс

```
OKX API Error 51008: Order value is too small
```

**Решение**: Увеличьте `FIXED_POSITION_SIZE` или пополните баланс

## Безопасность

1. **Никогда не делитесь API ключами**
2. **Используйте IP whitelist на OKX**
3. **Отключите вывод средств для API ключей**
4. **Начинайте с минимальных сумм**
5. **Тестируйте на demo минимум неделю**
6. **Установите разумные лимиты риска**

## Поддержка

- Документация OKX API: https://www.okx.com/docs-v5/en/
- Логи бота: `logs/trading_bot.log`
- Telegram уведомления: настройте для мониторинга

---

**Важно**: Это торговый бот. Торговля криптовалютами сопряжена с высоким риском. Используйте только те средства, которые можете позволить себе потерять.
