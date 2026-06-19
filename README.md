# OKX Supertrend Trading Bot

Production-ready automated trading bot for OKX using Supertrend indicator strategy.

## Features

- **OKX V5 API Integration**: Full support for OKX's latest API
- **Supertrend Strategy**: Trend-following strategy with customizable parameters
- **Risk Management**: Position sizing, daily loss limits, cooldown periods
- **Multiple Trading Modes**: Demo Trading, Paper Trading, Live Trading
- **Robust Error Handling**: Retry logic, rate limit handling, graceful shutdown
- **Comprehensive Logging**: Structured logging with file and console output
- **Optional Filters**: EMA and volume filters for signal confirmation
- **Unit Tests**: Test coverage for indicators and strategy logic

## Project Structure

```
okx-supertrend-bot/
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── okx_client.py          # OKX API wrapper
│   ├── indicators.py          # Technical indicators (Supertrend, ATR, EMA)
│   ├── strategy.py            # Trading strategy logic
│   ├── risk_manager.py        # Risk management
│   ├── trader.py              # Main trading engine
│   └── main.py                # Entry point
├── tests/
│   ├── __init__.py
│   ├── test_indicators.py     # Indicator tests
│   └── test_strategy.py       # Strategy tests
├── .env.example               # Environment variables template
├── .gitignore
├── requirements.txt
└── README.md
```

## Installation

### Prerequisites

- Python 3.11+
- OKX account (demo or live)
- API keys from OKX (with passphrase)

### Setup

1. **Clone or download the project**

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```env
OKX_API_KEY=your_api_key_here
OKX_API_SECRET=your_api_secret_here
OKX_PASSPHRASE=your_passphrase_here
TRADING_MODE=testnet  # testnet, paper, or live
SYMBOL=BTC-USDT-SWAP
TIMEFRAME=15
ATR_PERIOD=10
SUPERTREND_MULTIPLIER=3.0
RISK_PER_TRADE=1.0
MAX_POSITION_SIZE=1000.0
MAX_DAILY_LOSS=5.0
COOLDOWN_AFTER_LOSS=300
MIN_BALANCE=100.0
LOG_LEVEL=INFO
```

## Configuration

### Trading Parameters

- **SYMBOL**: Trading pair (e.g., BTC-USDT-SWAP for perpetual futures)
- **TIMEFRAME**: Candle timeframe in minutes (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, 1440)
- **ATR_PERIOD**: Period for ATR calculation (5-50)
- **SUPERTREND_MULTIPLIER**: Multiplier for Supertrend bands (1.0-10.0)

### Risk Management

- **RISK_PER_TRADE**: Risk percentage per trade (0.1-5.0%)
- **MAX_POSITION_SIZE**: Maximum position size in USDT
- **MAX_DAILY_LOSS**: Maximum daily loss percentage (1.0-20.0%)
- **COOLDOWN_AFTER_LOSS**: Cooldown period after loss in seconds
- **MIN_BALANCE**: Minimum required balance in USDT

### Trading Modes

1. **Demo Trading**: Uses OKX demo trading with test funds
2. **Paper**: Simulates trades without executing (logs only)
3. **Live**: Real trading with real money ⚠️

## Usage

### Run the bot

```bash
python -m src.main
```

### Run tests

```bash
pytest tests/ -v
```

### Run specific test file

```bash
pytest tests/test_indicators.py -v
```

## How It Works

### Strategy Logic

1. **Signal Generation**:
   - Calculates Supertrend indicator on closed candles
   - Generates LONG signal when Supertrend turns bullish (direction changes from -1 to 1)
   - Generates SHORT signal when Supertrend turns bearish (direction changes from 1 to -1)

2. **Entry Conditions**:
   - Supertrend direction must change (confirmed signal)
   - Optional EMA filter: only long above EMA 200, only short below
   - Optional volume filter: volume must exceed average by specified multiplier
   - No duplicate signals on same direction without significant price movement

3. **Exit Conditions**:
   - Opposite Supertrend signal (trend reversal)
   - Stop loss hit (placed below/above Supertrend with ATR buffer)
   - Take profit hit (optional, based on risk-reward ratio)

4. **Position Sizing**:
   - Calculated based on risk percentage and stop loss distance
   - Capped at maximum position size
   - Validated against account balance

5. **Risk Controls**:
   - Daily loss limit enforcement
   - Cooldown period after losses
   - Minimum balance check
   - One position at a time

### Workflow

```
1. Fetch latest klines (200 candles)
2. Calculate indicators (Supertrend, ATR, EMA, Volume SMA)
3. Wait for candle close
4. Check if Supertrend direction changed
5. Apply filters (EMA, volume)
6. Check risk management rules
7. Calculate position size and stop loss
8. Execute trade (if all conditions met)
9. Monitor position and update trailing stop
10. Close on opposite signal or stop hit
11. Record PnL and update statistics
12. Repeat
```

## API Endpoints Used

- `get_candlesticks`: Fetch historical candlestick data
- `get_ticker`: Get current price
- `get_account_balance`: Check account balance
- `get_positions`: Check open positions
- `place_order`: Open new position
- `set_leverage`: Set leverage (default 1x)

## Logging

Logs are saved to `logs/trading_bot.log` and displayed in console.

Log levels:
- **DEBUG**: Detailed calculation info
- **INFO**: Trading actions and status
- **WARNING**: Risk warnings and filtered signals
- **ERROR**: API errors and failures

## Safety Features

1. **Demo Trading First**: Always test on demo trading before live
2. **Paper Trading**: Simulate without executing orders
3. **Live Confirmation**: Requires explicit "YES" confirmation for live mode
4. **Daily Loss Limit**: Stops trading when limit reached
5. **Cooldown Period**: Prevents revenge trading after losses
6. **Position Validation**: Validates orders before execution
7. **Graceful Shutdown**: Handles Ctrl+C cleanly
8. **Error Recovery**: Retry logic for network errors

## Risks and Disclaimers

⚠️ **IMPORTANT WARNINGS**:

1. **Trading Risk**: Cryptocurrency trading involves substantial risk of loss
2. **No Guarantees**: Past performance does not guarantee future results
3. **Test Thoroughly**: Always test extensively on testnet before live trading
4. **Start Small**: Begin with minimal position sizes
5. **Monitor Actively**: Don't leave bot unattended for extended periods
6. **API Security**: Keep API keys secure, use IP whitelist on Bybit
7. **Market Conditions**: Strategy may not work in all market conditions
8. **Slippage**: Actual execution prices may differ from expected
9. **Bugs**: Software may contain bugs despite testing
10. **Responsibility**: You are solely responsible for your trading decisions

## Pre-Live Checklist

Before running in live mode:

- [ ] Tested extensively on demo trading (minimum 1 week)
- [ ] Reviewed all configuration parameters
- [ ] Verified API keys have correct permissions (no withdrawal)
- [ ] Set appropriate risk limits (start with 0.5% risk per trade)
- [ ] Enabled IP whitelist on OKX API settings
- [ ] Tested emergency shutdown (Ctrl+C)
- [ ] Monitored logs for errors
- [ ] Verified stop loss placement
- [ ] Checked position sizing calculations
- [ ] Understood strategy limitations
- [ ] Prepared to monitor actively
- [ ] Set up alerts for critical events

## Troubleshooting

### Common Issues

1. **API Authentication Error**
   - Verify API key, secret, and passphrase in `.env`
   - Check API key permissions on OKX
   - Ensure correct trading mode (demo vs live keys)

2. **Insufficient Balance**
   - Check minimum balance setting
   - Verify account has funds
   - Reduce position size or risk percentage

3. **No Signals Generated**
   - Check if Supertrend direction is changing
   - Verify filters aren't too restrictive
   - Ensure sufficient kline data (200+ candles)

4. **Rate Limit Errors**
   - Reduce polling frequency
   - Check OKX API rate limits
   - Implement longer delays between requests

5. **Position Not Opening**
   - Check risk management rules
   - Verify daily loss limit not reached
   - Check cooldown period
   - Review logs for validation errors

## Customization

### Modify Strategy

Edit `src/strategy.py` to customize:
- Signal generation logic
- Filter conditions
- Stop loss calculation
- Take profit calculation

### Add Indicators

Edit `src/indicators.py` to add:
- New technical indicators
- Custom calculations
- Additional filters

### Adjust Risk Rules

Edit `src/risk_manager.py` to modify:
- Position sizing algorithm
- Risk limits
- Cooldown logic

## Performance Optimization

1. **Reduce API Calls**: Increase polling interval
2. **Optimize Indicators**: Use vectorized calculations
3. **Cache Data**: Store recent klines to avoid refetching
4. **Async Operations**: Use asyncio for parallel requests

## Future Enhancements

Potential improvements:
- [ ] Backtesting engine with historical data
- [ ] Multiple timeframe analysis
- [ ] Portfolio management (multiple symbols)
- [ ] Telegram notifications
- [ ] Web dashboard for monitoring
- [ ] Machine learning signal filtering
- [ ] Advanced order types (trailing stop, OCO)
- [ ] Performance analytics and reporting
- [ ] Database integration for trade history
- [ ] Multi-exchange support

## Support

For issues and questions:
1. Check logs in `logs/trading_bot.log`
2. Review OKX API documentation
3. Test on demo trading first
4. Start with paper trading mode

## License

This software is provided as-is for educational purposes. Use at your own risk.

## Acknowledgments

- OKX for API access
- Python community for excellent libraries
- Supertrend indicator creators

---

**Remember**: Trading is risky. Never trade with money you can't afford to lose. This bot is a tool, not a guarantee of profits. Always do your own research and trade responsibly.
