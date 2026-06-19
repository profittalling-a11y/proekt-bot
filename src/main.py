"""Main entry point for the trading bot."""
import logging
import sys
from pathlib import Path
from threading import Thread

from .config import load_config
from .trader import TradingBot
from .dashboard_api import run_dashboard, set_bot_instance, set_config_instance, set_account_manager, set_multibot_manager
from .account_manager import AccountManager
from .multibot_manager import MultiBotManager


def setup_logging(log_level: str):
    """Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_dir / "trading_bot.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def main():
    """Main function."""
    try:
        # Load configuration
        config = load_config()

        # Setup logging
        setup_logging(config.log_level)

        logger = logging.getLogger(__name__)
        logger.info("Starting Multi-Exchange Trading Bot")

        # Initialize account manager
        account_manager = AccountManager()

        # Check if there's an active account
        active_account = account_manager.get_active_account()
        if active_account:
            logger.info(f"Loading active account: {active_account.name} ({active_account.exchange})")

            # Update config from active account
            from .config import Exchange as ExchangeEnum, TradingMode
            config.exchange = ExchangeEnum(active_account.exchange)
            config.set_api_credentials(
                active_account.api_key,
                active_account.api_secret,
                active_account.passphrase
            )
            config.timeframe = active_account.timeframe
            config.supertrend_multiplier = active_account.supertrend_multiplier
            config.trading_mode = TradingMode(active_account.trading_mode)

        # Validate configuration
        logger.info(f"Configuration loaded: {config.symbol} on {config.timeframe}m timeframe")
        logger.info(f"Trading mode: {config.trading_mode.value}")
        logger.info(f"Exchange: {config.exchange.value}")

        if config.is_live:
            logger.warning("=" * 60)
            logger.warning("LIVE TRADING MODE ENABLED")
            logger.warning("Real money will be used. Proceed with caution!")
            logger.warning("=" * 60)

        # Start dashboard in background thread
        logger.info("Starting dashboard on http://127.0.0.1:5000")
        dashboard_thread = Thread(target=run_dashboard, kwargs={'host': '127.0.0.1', 'port': 5000}, daemon=True)
        dashboard_thread.start()

        # Create bot instance (but don't start it)
        bot = TradingBot(config)

        # Initialize multi-bot manager
        multibot_manager = MultiBotManager(account_manager, config)

        # Set bot, config, account manager, and multibot manager instances for dashboard control
        set_bot_instance(bot)
        set_config_instance(config)
        set_account_manager(account_manager)
        set_multibot_manager(multibot_manager)

        logger.info("=" * 60)
        logger.info("Bot initialized. Use dashboard to start trading.")
        logger.info("Dashboard: http://127.0.0.1:5000")
        logger.info("Multi-bot mode: You can run multiple bots simultaneously")
        logger.info("=" * 60)

        # Keep main thread alive
        try:
            while True:
                dashboard_thread.join(timeout=1.0)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            multibot_manager.stop_all_bots()
            if bot.running:
                bot.stop()

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
