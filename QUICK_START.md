# 🚀 Быстрый запуск бота (без Telegram)

## Шаг 1: Установка Python

1. Скачайте Python 3.11+ с [python.org](https://www.python.org/downloads/)
2. Установите Python (отметьте "Add to PATH")
3. Проверьте установку:
   ```bash
   python --version
   ```

---

## Шаг 2: Установка зависимостей

Откройте командную строку в папке проекта:

```bash
# Создать виртуальное окружение
python -m venv venv

# Активировать (Windows)
venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt
```

---

## Шаг 3: Получить API ключи от Bybit Demo

### 3.1 Регистрация

1. Перейдите на [bybit.com](https://www.bybit.com)
2. Зарегистрируйтесь (email + пароль)
3. **Верификация НЕ требуется для Demo!**

### 3.2 Включить Demo Trading

1. Войдите в аккаунт Bybit
2. Перейдите в **Derivatives** → **USDT Perpetual**
3. В правом верхнем углу найдите переключатель **"Demo Trading"**
4. Включите Demo режим
5. Вам будет выдано **100,000 USDT** виртуальных денег

### 3.3 Создать API ключи

1. Перейдите в **Account** → **API Management**
2. Нажмите **Create New Key**
3. **Важно:** Выберите **Demo Trading** (не Mainnet!)
4. Настройте права:
   - ✅ **Read-Write**
   - ✅ **Contract Trading**
   - ❌ **Withdraw** (отключить)
5. IP whitelist (опционально):
   - Узнайте свой IP: [whatismyip.com](https://www.whatismyip.com)
   - Добавьте в whitelist
6. Нажмите **Submit**
7. **Сохраните API Key и Secret** (показываются только один раз!)

---

## Шаг 4: Настроить .env файл

Файл `.env` уже создан в папке проекта. Откройте его в блокноте и заполните:

```env
# Bybit API (Demo Trading)
BYBIT_API_KEY=ваш_api_key_сюда
BYBIT_API_SECRET=ваш_api_secret_сюда

# Режим: testnet для Demo Trading
TRADING_MODE=testnet

# Автосканирование ликвидных пар
AUTO_SCAN=true
MIN_VOLUME_24H=1000000
MAX_SYMBOLS=10

# Таймфрейм и индикаторы
TIMEFRAME=15
ATR_PERIOD=10
SUPERTREND_MULTIPLIER=3.0

# Риск-менеджмент
FIXED_POSITION_SIZE=1.0
RISK_PER_POSITION=2.0
MAX_POSITIONS=10
MAX_DAILY_LOSS=20.0

# Telegram (отключен)
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Логирование
LOG_LEVEL=INFO
```

**Важно:** Замените `ваш_api_key_сюда` и `ваш_api_secret_сюда` на реальные ключи из Bybit!

---

## Шаг 5: Запустить бота

```bash
# Убедитесь, что виртуальное окружение активировано
venv\Scripts\activate

# Запустить веб-сервер
python -m src.main
```

### Что вы увидите:

```
==========================================================
Bot initialized. Use dashboard to start trading.
Dashboard: http://127.0.0.1:5000
==========================================================

Auto-scanning markets for liquid pairs...
Found 45 liquid pairs

1. BTCUSDT: $5,234,567,890 volume
2. ETHUSDT: $2,456,789,012 volume
3. SOLUSDT: $1,234,567,890 volume
...

Configuration generated:
Symbols: BTCUSDT,ETHUSDT,SOLUSDT,...

Starting dashboard on http://127.0.0.1:5000
```

---

## Шаг 6: Открыть Dashboard и запустить торговлю

1. Откройте браузер
2. Перейдите на **http://127.0.0.1:5000**
3. Вы увидите dashboard с 5 карточками:
   - Баланс
   - Открытые позиции
   - Статистика сделок
   - Дневной PnL
   - Недельный PnL
4. Нажмите кнопку **"▶ Запустить"** для начала торговли
5. Бот начнет анализировать рынок и открывать позиции по сигналам Supertrend

---

## Шаг 7: Мониторинг

### Dashboard (обновляется каждые 2 секунды)

- **Баланс и Equity** - текущий баланс счета
- **Открытые позиции** - активные сделки с PnL
- **Статистика** - винрейт, прибыль/убыток
- **Графики PnL** - дневная и недельная динамика

### Логи

Проверьте файл `logs/trading_bot.log`:

```
2026-05-15 20:13:45 | INFO | Trading bot started
2026-05-15 20:13:46 | INFO | Balance: 100000.00 USDT
2026-05-15 20:13:50 | INFO | New candle closed
2026-05-15 20:14:00 | INFO | Supertrend direction changed: -1 -> 1
2026-05-15 20:14:01 | INFO | LONG signal generated
2026-05-15 20:14:02 | INFO | Opening LONG: qty=0.001, entry=50000.00
```

---

## Управление ботом

### Остановить торговлю

Нажмите кнопку **"⏹ Остановить"** на dashboard.

### Перезапустить торговлю

Нажмите кнопку **"▶ Запустить"** снова.

### Закрыть веб-сервер

Нажмите `Ctrl+C` в командной строке (это также остановит торговлю).

---

## ⚠️ Важные моменты

### 1. Начните с Demo!

- ✅ Тестируйте минимум **1-2 недели** на Demo
- ✅ Убедитесь, что бот работает стабильно
- ✅ Проверьте все сценарии

### 2. Плечо 50x очень рискованно!

- ⚠️ Движение на 2% против вас = ликвидация
- ✅ Начните с консервативных настроек
- ✅ Увеличивайте постепенно

### 3. Мониторинг обязателен!

- ✅ Проверяйте Dashboard регулярно
- ✅ Следите за логами
- ✅ Первые дни мониторьте активно

### 4. Консервативные настройки для начала

Если хотите снизить риск, измените в `.env`:

```env
FIXED_POSITION_SIZE=1.0      # 1 USDT маржа
RISK_PER_POSITION=1.5        # 1.5% stop loss
MAX_POSITIONS=5              # Максимум 5 позиций
MAX_DAILY_LOSS=10.0          # 10% дневной лимит
MAX_SYMBOLS=5                # Меньше пар
```

---

## 🐛 Решение проблем

### Ошибка: "API Authentication failed"

**Решение:**
1. Проверьте API Key и Secret в `.env`
2. Убедитесь, что ключи для **Demo Trading** (не Mainnet)
3. Проверьте IP whitelist на Bybit

### Ошибка: "Insufficient balance"

**Решение:**
1. Проверьте баланс на Demo счете (должно быть 100,000 USDT)
2. Уменьшите `FIXED_POSITION_SIZE` в `.env`
3. Уменьшите `MAX_POSITIONS`

### Бот не открывает позиции

**Причины:**
1. Нет сигналов Supertrend (нужно ждать)
2. Риск-лимиты достигнуты
3. Cooldown после убытка активен

**Проверьте логи:**
```
Trading not allowed: Daily loss limit reached
```

### Dashboard не открывается

**Решение:**
1. Проверьте, что бот запущен (`python -m src.main`)
2. Откройте http://127.0.0.1:5000 (не https)
3. Проверьте, что порт 5000 свободен

---

## ✅ Чеклист перед запуском

- [ ] Python 3.11+ установлен
- [ ] Виртуальное окружение создано и активировано
- [ ] Зависимости установлены (`pip install -r requirements.txt`)
- [ ] Bybit Demo Trading включен
- [ ] API ключи созданы для Demo Trading
- [ ] API ключи добавлены в `.env`
- [ ] `TELEGRAM_ENABLED=false` в `.env`
- [ ] Веб-сервер запущен (`python -m src.main`)
- [ ] Dashboard открывается (http://127.0.0.1:5000)
- [ ] Кнопка "Запустить" нажата
- [ ] Логи пишутся в `logs/trading_bot.log`

---

## 🎯 Что дальше?

1. **Мониторьте первые 24 часа** - проверяйте каждую сделку
2. **Анализируйте результаты** - винрейт, PnL, drawdown
3. **Оптимизируйте параметры** - таймфрейм, плечо, риск
4. **Добавьте Telegram** - см. `TELEGRAM_SETUP.md`
5. **Только потом Live** - с минимальным депозитом

---

**Удачной торговли! 🚀**

*Помните: это инструмент, а не гарантия прибыли. Торгуйте ответственно!*
