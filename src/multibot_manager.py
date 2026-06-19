"""Multi-bot manager for running multiple bots simultaneously."""
import logging
import threading
from typing import Dict, Optional, List
from datetime import datetime

from .trader import TradingBot
from .config import Config
from .account_manager import AccountManager

logger = logging.getLogger(__name__)


class BotInstance:
    """Represents a single bot instance."""

    def __init__(self, bot_id: str, account_id: str, account_name: str, symbol: str, bot: TradingBot):
        """Initialize bot instance.

        Args:
            bot_id: Unique bot ID
            account_id: Account ID
            account_name: Account name
            symbol: Trading symbol
            bot: TradingBot instance
        """
        self.bot_id = bot_id
        self.account_id = account_id
        self.account_name = account_name
        self.symbol = symbol
        self.bot = bot
        self.thread: Optional[threading.Thread] = None
        self.started_at: Optional[str] = None

    def start(self):
        """Start bot in separate thread."""
        if self.thread and self.thread.is_alive():
            logger.warning(f"Bot {self.bot_id} is already running")
            return False

        self.thread = threading.Thread(
            target=self.bot.start,
            name=f"Bot-{self.bot_id}",
            daemon=True
        )
        self.thread.start()
        self.started_at = datetime.now().isoformat()

        logger.info(f"Bot started: {self.bot_id} ({self.symbol} on {self.account_name})")
        return True

    def stop(self):
        """Stop bot."""
        if not self.thread or not self.thread.is_alive():
            logger.warning(f"Bot {self.bot_id} is not running")
            # Force set running to False
            if self.bot:
                self.bot.running = False
            return False

        self.bot.stop()
        self.thread.join(timeout=5)

        # Ensure bot is marked as stopped
        if self.bot:
            self.bot.running = False

        logger.info(f"Bot stopped: {self.bot_id}")
        return True

    def is_running(self) -> bool:
        """Check if bot is running.

        Returns:
            True if running
        """
        return self.bot.running if self.bot else False

    def get_status(self) -> Dict:
        """Get bot status.

        Returns:
            Status dictionary
        """
        return {
            "bot_id": self.bot_id,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "symbol": self.symbol,
            "is_running": self.is_running(),
            "started_at": self.started_at,
            "exchange": self.bot.config.exchange.value if self.bot else None,
            "timeframe": self.bot.config.timeframe if self.bot else None,
            "supertrend_multiplier": self.bot.config.supertrend_multiplier if self.bot else None,
            "atr_period": self.bot.config.atr_period if self.bot else None,
        }


class MultiBotManager:
    """Manager for multiple bot instances."""

    def __init__(self, account_manager: AccountManager, base_config: Config):
        """Initialize multi-bot manager.

        Args:
            account_manager: Account manager instance
            base_config: Base configuration
        """
        self.account_manager = account_manager
        self.base_config = base_config
        self.bots: Dict[str, BotInstance] = {}
        self.lock = threading.Lock()

        logger.info("Multi-bot manager initialized")

    def create_bot_for_account(self, account_id: str, symbol: str = None, timeframe: int = None, supertrend_multiplier: float = None) -> Optional[BotInstance]:
        """Create bot instance for account with custom settings.

        Args:
            account_id: Account ID
            symbol: Trading symbol (optional, uses account default if not provided)
            timeframe: Timeframe in minutes (optional)
            supertrend_multiplier: Supertrend multiplier (optional)

        Returns:
            BotInstance or None if account not found
        """
        account = self.account_manager.get_account(account_id)

        if not account:
            logger.error(f"Account not found: {account_id}")
            return None

        # Create config for this account
        from .config import Config, Exchange as ExchangeEnum, TradingMode

        config = Config()

        # Copy base config settings
        config.atr_period = self.base_config.atr_period
        config.risk_per_position = self.base_config.risk_per_position
        config.fixed_position_size = self.base_config.fixed_position_size
        config.max_positions = self.base_config.max_positions
        config.max_daily_loss = self.base_config.max_daily_loss
        config.cooldown_after_loss = self.base_config.cooldown_after_loss
        config.min_balance = self.base_config.min_balance
        config.telegram_enabled = self.base_config.telegram_enabled
        config.telegram_bot_token = self.base_config.telegram_bot_token
        config.telegram_chat_id = self.base_config.telegram_chat_id

        # Set account-specific settings
        config.exchange = ExchangeEnum(account.exchange)
        config.set_api_credentials(
            account.api_key,
            account.api_secret,
            account.passphrase
        )

        # Use custom settings or account defaults
        config.symbols = symbol if symbol else (account.symbol if hasattr(account, 'symbol') else 'BTC-USDT-SWAP')
        config.timeframe = timeframe if timeframe else account.timeframe
        config.supertrend_multiplier = supertrend_multiplier if supertrend_multiplier else account.supertrend_multiplier
        config.trading_mode = TradingMode(account.trading_mode)

        # Create bot
        bot = TradingBot(config)

        # Generate unique bot ID - include symbol to make it unique
        import time
        bot_id = f"{account_id}_{config.symbols}_{config.timeframe}_{config.supertrend_multiplier}_{int(time.time() * 1000)}"

        # Create bot instance
        bot_instance = BotInstance(
            bot_id=bot_id,
            account_id=account_id,
            account_name=account.name,
            symbol=config.symbols,
            bot=bot
        )

        return bot_instance

    def start_bot(self, account_id: str, symbol: str = None, timeframe: int = None, supertrend_multiplier: float = None) -> str:
        """Start bot for account with custom settings.

        Args:
            account_id: Account ID
            symbol: Trading symbol (optional)
            timeframe: Timeframe in minutes (optional)
            supertrend_multiplier: Supertrend multiplier (optional)

        Returns:
            Bot ID if started successfully

        Raises:
            Exception if bot cannot be started
        """
        with self.lock:
            # Create new bot instance
            bot_instance = self.create_bot_for_account(account_id, symbol, timeframe, supertrend_multiplier)

            if not bot_instance:
                raise Exception(f"Failed to create bot for account {account_id}")

            bot_id = bot_instance.bot_id

            # Check if a bot with same configuration (not same ID) already exists and is running
            for existing_id, existing_bot in list(self.bots.items()):
                if (existing_bot.account_id == account_id and
                    existing_bot.symbol == symbol and
                    existing_bot.is_running()):
                    logger.warning(f"Bot for {symbol} on account {account_id} is already running with ID {existing_id}")
                    # Don't raise exception, just return existing bot_id
                    return existing_id

            # Start bot
            success = bot_instance.start()

            if success:
                self.bots[bot_id] = bot_instance
                logger.info(f"Bot started successfully: {bot_id}")
                return bot_id
            else:
                raise Exception(f"Failed to start bot {bot_id}")

    def stop_bot(self, bot_id: str) -> bool:
        """Stop bot by bot ID.

        Args:
            bot_id: Bot ID

        Returns:
            True if stopped successfully
        """
        with self.lock:
            if bot_id not in self.bots:
                logger.warning(f"Bot {bot_id} not found")
                return False

            bot_instance = self.bots[bot_id]
            success = bot_instance.stop()

            if success:
                del self.bots[bot_id]

            return success

    def stop_all_bots(self):
        """Stop all running bots."""
        with self.lock:
            bot_ids = list(self.bots.keys())

            for bot_id in bot_ids:
                self.stop_bot(bot_id)

            logger.info("All bots stopped")

    def get_running_bots(self) -> List[Dict]:
        """Get list of running bots.

        Returns:
            List of bot status dictionaries
        """
        with self.lock:
            return [
                bot_instance.get_status()
                for bot_instance in self.bots.values()
            ]

    def get_bot_instance(self, account_id: str) -> Optional[BotInstance]:
        """Get bot instance by account ID.

        Args:
            account_id: Account ID

        Returns:
            BotInstance or None
        """
        return self.bots.get(account_id)

    def is_bot_running(self, account_id: str) -> bool:
        """Check if bot is running for account.

        Args:
            account_id: Account ID

        Returns:
            True if running
        """
        bot_instance = self.bots.get(account_id)
        return bot_instance.is_running() if bot_instance else False

    def get_bot_count(self) -> int:
        """Get number of running bots.

        Returns:
            Number of running bots
        """
        return len(self.bots)

    def start_bots_for_all_pairs(self, account_id: str) -> Dict:
        """Start bots for all trading pairs from leverage config.

        Args:
            account_id: Account ID

        Returns:
            Dictionary with results
        """
        account = self.account_manager.get_account(account_id)

        if not account:
            logger.error(f"Account not found: {account_id}")
            return {
                'success': False,
                'error': 'Account not found',
                'started': 0,
                'failed': 0
            }

        # Get trading pairs from leverage config
        pairs = []
        if hasattr(self.base_config, 'leverage_config') and self.base_config.leverage_config:
            leverage_pairs = self.base_config.leverage_config.split(',')
            for pair in leverage_pairs:
                if ':' in pair:
                    symbol = pair.split(':')[0].strip()
                    pairs.append(symbol)

        if not pairs:
            logger.warning("No trading pairs found in leverage config")
            return {
                'success': False,
                'error': 'No trading pairs configured',
                'started': 0,
                'failed': 0
            }

        logger.info(f"Starting bots for {len(pairs)} pairs: {', '.join(pairs)}")

        started = 0
        failed = 0

        for symbol in pairs:
            try:
                # Create unique bot ID for this account+symbol combination
                bot_id = f"{account_id}_{symbol}"

                # Check if bot already running
                if bot_id in self.bots and self.bots[bot_id].is_running():
                    logger.info(f"Bot already running for {symbol}")
                    started += 1
                    continue

                # Create config for this symbol
                from .config import Config, Exchange as ExchangeEnum, TradingMode

                config = Config()

                # Copy base config settings
                config.atr_period = self.base_config.atr_period
                config.risk_per_position = self.base_config.risk_per_position
                config.fixed_position_size = self.base_config.fixed_position_size
                config.max_positions = self.base_config.max_positions
                config.max_daily_loss = self.base_config.max_daily_loss
                config.cooldown_after_loss = self.base_config.cooldown_after_loss
                config.min_balance = self.base_config.min_balance
                config.telegram_enabled = self.base_config.telegram_enabled
                config.telegram_bot_token = self.base_config.telegram_bot_token
                config.telegram_chat_id = self.base_config.telegram_chat_id
                config.leverage_config = self.base_config.leverage_config

                # Set account-specific settings
                config.exchange = ExchangeEnum(account.exchange)
                config.set_api_credentials(
                    account.api_key,
                    account.api_secret,
                    account.passphrase
                )
                config.timeframe = account.timeframe
                config.supertrend_multiplier = account.supertrend_multiplier
                config.trading_mode = TradingMode(account.trading_mode)

                # Set symbol for this bot (use 'symbols' field, not 'symbol')
                config.symbols = symbol

                # Create bot
                bot = TradingBot(config)

                # Create bot instance
                bot_instance = BotInstance(
                    bot_id=bot_id,
                    account_id=account_id,
                    account_name=f"{account.name} - {symbol}",
                    symbol=symbol,
                    bot=bot
                )

                # Start bot
                if bot_instance.start():
                    self.bots[bot_id] = bot_instance
                    started += 1
                    logger.info(f"Bot started for {symbol}")
                else:
                    failed += 1
                    logger.error(f"Failed to start bot for {symbol}")

            except Exception as e:
                failed += 1
                logger.error(f"Error starting bot for {symbol}: {e}")

        logger.info(f"Started {started}/{len(pairs)} bots, {failed} failed")

        return {
            'success': started > 0,
            'started': started,
            'failed': failed,
            'total': len(pairs)
        }
