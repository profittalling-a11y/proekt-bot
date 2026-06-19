# Multi-Exchange Supertrend Trading Bot

Автоматический торговый бот для криптовалютных бирж (OKX, Bybit, BingX) с стратегией Supertrend.

## Возможности

- **3 биржи**: OKX, Bybit, BingX — переключение через dashboard
- **Стратегия Supertrend**: трендовая стратегия с настраиваемыми параметрами
- **Управление рисками**: фиксированный размер позиции, дневной лимит убытков, кулдаун
- **Мультибот**: запуск нескольких ботов одновременно на разных парах
- **Веб-дашборд**: мониторинг и управление через браузер (Flask)
- **Telegram-уведомления**: открытие/закрытие позиций, ошибки, дневной отчёт
- **TradingView Webhook**: автоматическая торговля по сигналам TradingView
- **Автосканер рынков**: автоматический поиск ликвидных пар
- **Тесты**: 62 unit-теста

## Структура проекта

```
src/
├── config.py              # Конфигурация (Pydantic)
├── main.py                # Точка входа
├── trader.py              # Торговый движок
├── strategy.py            # Стратегия Supertrend
├── risk_manager.py        # Управление рисками
├── indicators.py          # Индикаторы (ATR, Supertrend, EMA)
├── exchange_client.py     # Базовый класс биржи (ABC)
├── okx_client.py          # OKX V5 API
├── bybit_client.py        # Bybit V5 API
├── bingx_client.py        # BingX API
├── exchange_factory.py    # Фабрика клиентов
├── dashboard_api.py       # Flask API дашборда
├── account_manager.py     # Менеджер аккаунтов
├── multibot_manager.py    # Мультибот менеджер
├── trade_history.py       # История сделок
├── market_scanner.py      # Сканер рынков
├── telegram_notifier.py   # Telegram уведомления
├── tradingview_webhook.py # TradingView webhook
└── main_webhook.py        # Webhook сервер
tests/
├── test_indicators.py     # Тесты индикаторов
├── test_strategy.py       # Тесты стратегии
├── test_risk_manager.py   # Тесты риск-менеджера
└── test_config.py         # Тесты конфигурации
templates/
└── dashboard.html         # Веб-дашборд
```

## Установка

### Требования

- Python 3.11+
- Аккаунт на OKX, Bybit или BingX
- API ключи биржи

### Настройка

```bash
# Клонировать
git clone https://github.com/profittalling-a11y/proekt-bot.git
cd proekt-bot

# Виртуальное окружение
python -m venv venv
venv\Scripts\activate

# Зависимости
pip install -r requirements.txt

# Конфигурация
cp .env.example .env
```

Отредактируйте `.env`:

```env
EXCHANGE=okx                    # okx, bybit, bingx
TRADING_MODE=testnet            # testnet, paper, live

# OKX
OKX_API_KEY=...
OKX_API_SECRET=...
OKX_PASSPHRASE=...

# Bybit
BYBIT_API_KEY=...
BYBIT_API_SECRET=...

# BingX
BINGX_API_KEY=...
BINGX_API_SECRET=...

# Торговые параметры
SYMBOLS=BTC-USDT-SWAP,ETH-USDT-SWAP
TIMEFRAME=15
ATR_PERIOD=10
SUPERTREND_MULTIPLIER=3.0
POLLING_INTERVAL=30

# Управление рисками
FIXED_POSITION_SIZE=1.0
MAX_POSITIONS=10
MAX_DAILY_LOSS=20.0
LEVERAGE_CONFIG=BTC-USDT-SWAP:50,ETH-USDT-SWAP:50

# Telegram (опционально)
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Запуск

```bash
# Основной бот + дашборд
python -m src.main

# Только webhook-сервер (TradingView)
python -m src.main_webhook
```

Дашборд: http://127.0.0.1:5000

## Тесты

```bash
pytest tests/ -v
```

## Стратегия

1. Рассчитывает Supertrend на закрытых свечах
2. LONG когда Supertrend разворачивается вверх (направление -1 -> 1)
3. SHORT когда Supertrend разворачивается вниз (направление 1 -> -1)
4. Опциональные фильтры: EMA 200, объём
5. Stop loss по swing low/high + буфер ATR
6. Take profit по рыночному сигналу (без фиксированного TP)

## Управление рисками

- Фиксированный размер позиции, масштабируется с балансом (каждые 100 USDT = 1x)
- Дневной лимит убытков (по умолчанию 20%)
- Кулдаун после убытка (300 сек)
- Минимальный баланс для торговли
- Валидация ордеров перед исполнением

## Лицензия

Для образовательных целей. Используйте на свой риск.
