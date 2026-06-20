"""Main entry point for the trading bot."""
import logging
import sys
from pathlib import Path
from threading import Thread

from .config import load_config
from .dashboard_api import run_dashboard, set_config_instance, set_account_manager, set_multibot_manager
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

        # Start dashboard + webhook in background thread
        logger.info("Starting dashboard + webhook on http://0.0.0.0:80")
        dashboard_thread = Thread(target=run_dashboard, kwargs={'host': '0.0.0.0', 'port': 80}, daemon=True)
        dashboard_thread.start()

        # Initialize account manager and multi-bot manager
        account_manager = AccountManager()
        multibot_manager = MultiBotManager(account_manager, config)

        # Don't create bot instance yet - wait for user to connect exchange via dashboard
        set_config_instance(config)
        set_account_manager(account_manager)
        set_multibot_manager(multibot_manager)

        logger.info("=" * 60)
        logger.info("Bot initialized. Connect exchange via dashboard to start trading.")
        logger.info("Dashboard + Webhook: http://0.0.0.0:80")
        logger.info("=" * 60)

        # Keep main thread alive
        try:
            while True:
                dashboard_thread.join(timeout=1.0)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            multibot_manager.stop_all_bots()

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
