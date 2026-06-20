"""Configuration management using Pydantic."""
import logging
from enum import Enum
from typing import List, Dict
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class TradingMode(str, Enum):
    TESTNET = "testnet"
    PAPER = "paper"
    LIVE = "live"


class Exchange(str, Enum):
    OKX = "okx"
    BYBIT = "bybit"
    BINGX = "bingx"
    GATE = "gate"
    BITGET = "bitget"
    PIONEX = "pionex"
    WEEX = "weex"
    TOOBIT = "toobit"


class Config(BaseSettings):
    """Bot configuration with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Exchange Selection
    exchange: Exchange = Field(default=Exchange.OKX, description="Exchange to use")

    # API Credentials - will be set dynamically from dashboard
    api_key: str = Field(default="", description="Exchange API Key")
    api_secret: str = Field(default="", description="Exchange API Secret")
    api_passphrase: str = Field(default="", description="API Passphrase (OKX only)")

    # Legacy support for .env file
    okx_api_key: str = Field(default="", description="OKX API Key")
    okx_api_secret: str = Field(default="", description="OKX API Secret")
    okx_passphrase: str = Field(default="", description="OKX API Passphrase")

    bybit_api_key: str = Field(default="", description="Bybit API Key")
    bybit_api_secret: str = Field(default="", description="Bybit API Secret")

    bingx_api_key: str = Field(default="", description="BingX API Key")
    bingx_api_secret: str = Field(default="", description="BingX API Secret")

    gate_api_key: str = Field(default="", description="Gate.io API Key")
    gate_api_secret: str = Field(default="", description="Gate.io API Secret")

    bitget_api_key: str = Field(default="", description="Bitget API Key")
    bitget_api_secret: str = Field(default="", description="Bitget API Secret")
    bitget_passphrase: str = Field(default="", description="Bitget API Passphrase")

    pionex_api_key: str = Field(default="", description="Pionex API Key")
    pionex_api_secret: str = Field(default="", description="Pionex API Secret")

    weex_api_key: str = Field(default="", description="Weex API Key")
    weex_api_secret: str = Field(default="", description="Weex API Secret")

    toobit_api_key: str = Field(default="", description="Toobit API Key")
    toobit_api_secret: str = Field(default="", description="Toobit API Secret")

    # Trading Mode
    trading_mode: TradingMode = Field(default=TradingMode.TESTNET)

    # Market Scanning
    auto_scan: bool = Field(default=True, description="Auto-scan liquid markets")
    min_volume_24h: float = Field(default=1_000_000, gt=0, description="Minimum 24h volume in USDT")
    max_symbols: int = Field(default=10, ge=1, le=50, description="Maximum symbols to trade")

    # Trading Parameters
    symbols: str = Field(default="BTC-USDT-SWAP,ETH-USDT-SWAP", description="Comma-separated trading pairs")
    timeframe: int = Field(default=15, description="Timeframe in minutes")
    atr_period: int = Field(default=10, ge=5, le=50, description="ATR period")
    supertrend_multiplier: float = Field(default=3.0, ge=1.0, le=10.0)
    polling_interval: int = Field(default=30, ge=5, le=300, description="Polling interval in seconds")

    # Risk Management - Fixed Position Sizing
    fixed_position_size: float = Field(default=1.0, gt=0, description="Fixed position size in USDT")
    risk_per_position: float = Field(default=2.0, ge=0.5, le=5.0, description="Risk % per position")
    max_positions: int = Field(default=10, ge=1, le=20, description="Maximum open positions")

    # Leverage Configuration
    leverage_config: str = Field(
        default="BTC-USDT-SWAP:50,ETH-USDT-SWAP:50,SOL-USDT-SWAP:25",
        description="Leverage per symbol (SYMBOL:LEVERAGE,SYMBOL:LEVERAGE)"
    )

    # Risk Management - Account Level
    max_daily_loss: float = Field(default=20.0, ge=1.0, le=50.0, description="Max daily loss %")
    cooldown_after_loss: int = Field(default=300, ge=0, description="Cooldown in seconds")
    min_balance: float = Field(default=10.0, gt=0, description="Minimum balance in USDT")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Telegram Notifications
    telegram_enabled: bool = Field(default=False, description="Enable Telegram notifications")
    telegram_bot_token: str = Field(default="", description="Telegram bot token")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID")

    # Optional filters
    use_ema_filter: bool = Field(default=False, description="Use EMA 200 filter")
    ema_period: int = Field(default=200, ge=50, le=500)
    use_volume_filter: bool = Field(default=False, description="Use volume filter")
    min_volume_multiplier: float = Field(default=1.5, ge=1.0, le=5.0)

    # TradingView Webhook Settings
    tradingview_webhook_secret: str = Field(default="", description="Webhook secret for signature verification")
    webhook_port: int = Field(default=5001, ge=1024, le=65535, description="Webhook server port")

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: str) -> str:
        """Ensure symbols are uppercase and normalized to OKX format."""
        if not v:
            return v
        symbols = []
        for s in v.split(','):
            s = s.strip().upper()
            # Normalize to OKX format if needed
            if s and not s.endswith("-SWAP"):
                if "-" not in s and s.endswith("USDT"):
                    # Convert BTCUSDT to BTC-USDT-SWAP
                    base = s[:-4]
                    s = f"{base}-USDT-SWAP"
                elif not s.endswith("-SWAP"):
                    s = f"{s}-SWAP"
            symbols.append(s)
        return ','.join(symbols)

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe_values(cls, v: int) -> int:
        """Validate timeframe is supported."""
        valid_timeframes = [5, 10, 15, 30, 60, 120, 240, 360, 720, 1440]
        if v not in valid_timeframes:
            raise ValueError(f"Timeframe must be one of {valid_timeframes}")
        return v

    def get_api_credentials(self) -> Dict[str, str]:
        """Get API credentials for selected exchange.

        Returns:
            Dictionary with api_key, api_secret, and optionally passphrase
        """
        # If dynamic credentials are set, use them
        if self.api_key and self.api_secret:
            creds = {
                "api_key": self.api_key,
                "api_secret": self.api_secret,
            }
            if self.api_passphrase:
                creds["passphrase"] = self.api_passphrase
            return creds

        # Otherwise, use exchange-specific credentials from .env
        if self.exchange == Exchange.OKX:
            return {
                "api_key": self.okx_api_key,
                "api_secret": self.okx_api_secret,
                "passphrase": self.okx_passphrase,
            }
        elif self.exchange == Exchange.BYBIT:
            return {
                "api_key": self.bybit_api_key,
                "api_secret": self.bybit_api_secret,
            }
        elif self.exchange == Exchange.BINGX:
            return {
                "api_key": self.bingx_api_key,
                "api_secret": self.bingx_api_secret,
            }
        elif self.exchange == Exchange.GATE:
            return {
                "api_key": self.gate_api_key,
                "api_secret": self.gate_api_secret,
            }
        elif self.exchange == Exchange.BITGET:
            creds = {
                "api_key": self.bitget_api_key,
                "api_secret": self.bitget_api_secret,
            }
            if self.bitget_passphrase:
                creds["passphrase"] = self.bitget_passphrase
            return creds
        elif self.exchange == Exchange.PIONEX:
            return {
                "api_key": self.pionex_api_key,
                "api_secret": self.pionex_api_secret,
            }
        elif self.exchange == Exchange.WEEX:
            return {
                "api_key": self.weex_api_key,
                "api_secret": self.weex_api_secret,
            }
        elif self.exchange == Exchange.TOOBIT:
            return {
                "api_key": self.toobit_api_key,
                "api_secret": self.toobit_api_secret,
            }

        return {}

    def set_api_credentials(self, api_key: str, api_secret: str, passphrase: str = ""):
        """Set API credentials dynamically.

        Args:
            api_key: API key
            api_secret: API secret
            passphrase: API passphrase (for OKX)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = passphrase

    def set_trading_params(self, timeframe: int, supertrend_multiplier: float):
        """Set trading parameters dynamically.

        Args:
            timeframe: Timeframe in minutes
            supertrend_multiplier: Supertrend multiplier
        """
        self.timeframe = timeframe
        self.supertrend_multiplier = supertrend_multiplier

    @property
    def symbol(self) -> str:
        """Alias for 'symbols' – для совместимости со старым кодом, который использует config.symbol."""
        return self.symbols

    @property
    def symbol_list(self) -> List[str]:
        """Get list of trading symbols."""
        return [s.strip() for s in self.symbols.split(',')]

    @property
    def leverage_map(self) -> Dict[str, int]:
        """Parse leverage configuration into dictionary.

        Returns:
            Dictionary mapping symbol to leverage
        """
        leverage_dict = {}
        if self.leverage_config:
            pairs = self.leverage_config.split(',')
            for pair in pairs:
                if ':' in pair:
                    symbol, leverage = pair.split(':')
                    symbol = symbol.strip().upper()
                    try:
                        leverage_dict[symbol] = int(leverage.strip())
                    except ValueError:
                        pass
        return leverage_dict

    @property
    def is_testnet(self) -> bool:
        """Check if running in testnet mode."""
        return self.trading_mode == TradingMode.TESTNET

    @property
    def is_paper_trading(self) -> bool:
        """Check if running in paper trading mode."""
        return self.trading_mode == TradingMode.PAPER

    @property
    def is_live(self) -> bool:
        """Check if running in live mode."""
        return self.trading_mode == TradingMode.LIVE

    @property
    def exchange_base_url(self) -> str:
        """Get exchange API base URL based on mode."""
        if self.exchange == Exchange.OKX:
            return "https://www.okx.com"
        elif self.exchange == Exchange.BYBIT:
            if self.is_testnet:
                return "https://api-testnet.bybit.com"
            return "https://api.bybit.com"
        elif self.exchange == Exchange.BINGX:
            return "https://open-api.bingx.com"
        return ""

    def get_interval_string(self) -> str:
        """Convert timeframe to exchange interval string."""
        if self.exchange == Exchange.OKX:
            # OKX format: 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D
            if self.timeframe < 60:
                return f"{self.timeframe}m"
            elif self.timeframe < 1440:
                hours = self.timeframe // 60
                return f"{hours}H"
            else:
                return "1D"
        elif self.exchange == Exchange.BYBIT:
            # Bybit format: 1, 5, 15, 30, 60, 120, 240, D
            if self.timeframe < 60:
                return str(self.timeframe)
            elif self.timeframe < 1440:
                return str(self.timeframe)
            else:
                return "D"
        elif self.exchange == Exchange.BINGX:
            # BingX format: 1m, 5m, 15m, 30m, 1h, 4h, 1d
            if self.timeframe < 60:
                return f"{self.timeframe}m"
            elif self.timeframe < 1440:
                hours = self.timeframe // 60
                return f"{hours}h"
            else:
                return "1d"
        return str(self.timeframe)

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to exchange-specific format.

        Args:
            symbol: Symbol in any format

        Returns:
            Symbol in exchange-specific format
        """
        from .symbol_utils import normalize_symbol as _normalize
        return _normalize(symbol, self.exchange)

    def get_leverage_for_symbol(self, symbol: str) -> int:
        """Get leverage for specific symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Leverage value (default 50 if not specified)
        """
        # Normalize symbol before lookup
        symbol = self.normalize_symbol(symbol)
        leverage_map = self.leverage_map
        return leverage_map.get(symbol, 50)  # Default 50x if not specified

    def calculate_position_size_for_balance(self, balance: float) -> float:
        """Calculate position size based on current balance.

        For every 100 USDT, position size increases by fixed_position_size.

        Examples:
            balance=100 → 1 USDT
            balance=150 → 1 USDT
            balance=200 → 2 USDT
            balance=350 → 3 USDT

        Args:
            balance: Current balance

        Returns:
            Position size in USDT
        """
        multiplier = int(balance / 100)
        if multiplier < 1:
            multiplier = 1
        return self.fixed_position_size * multiplier

    def scan_and_update_symbols(self) -> bool:
        """Scan markets and update symbols if auto_scan is enabled.

        Returns:
            True if symbols were updated
        """
        if not self.auto_scan:
            return False

        try:
            from .market_scanner import scan_markets

            logger.info("Auto-scanning markets for liquid pairs...")

            creds = self.get_api_credentials()

            result = scan_markets(
                exchange=self.exchange.value,
                api_key=creds.get("api_key", ""),
                api_secret=creds.get("api_secret", ""),
                passphrase=creds.get("passphrase", ""),
                testnet=self.is_testnet
            )

            if result and result.get("symbols"):
                # Update symbols
                self.symbols = result["symbols_str"]

                # Update leverage config
                if result.get("leverage_config"):
                    self.leverage_config = result["leverage_config"]

                logger.info(f"Auto-scan complete: {len(result['symbols'])} symbols configured")
                return True
            else:
                logger.warning("Auto-scan found no symbols, using manual config")
                return False

        except Exception as e:
            logger.error(f"Error during auto-scan: {e}")
            logger.info("Falling back to manual symbols configuration")
            return False


def load_config() -> Config:
    """Load and validate configuration."""
    config = Config()

    # Auto-scan markets if enabled
    if config.auto_scan:
        config.scan_and_update_symbols()

    return config