"""Main entry point for TradingView webhook server."""
import logging
import sys
from pathlib import Path
from flask import Flask

from src.config import load_config
from src.tradingview_webhook import webhook_bp, init_webhook_handler


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
            logging.FileHandler(log_dir / "webhook.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)


def main():
    """Main function."""
    try:
        # Load configuration
        config = load_config()

        # Setup logging
        setup_logging(config.log_level)

        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("TRADINGVIEW WEBHOOK SERVER STARTING")
        logger.info("=" * 60)

        # Initialize webhook handler
        init_webhook_handler(config)

        # Get webhook port from config or use default
        webhook_port = getattr(config, 'webhook_port', 5001)

        # Create Flask app
        app = Flask(__name__)
        app.register_blueprint(webhook_bp)

        # Add health check endpoint
        @app.route('/health', methods=['GET'])
        def health_check():
            return {'status': 'ok', 'message': 'Webhook server is running'}, 200

        # Print startup info
        logger.info(f"Exchange: {config.exchange.value.upper()}")
        logger.info(f"Trading mode: {config.trading_mode.value.upper()}")
        logger.info(f"Webhook URL: http://0.0.0.0:{webhook_port}/tradingview/webhook")
        logger.info(f"Health check: http://0.0.0.0:{webhook_port}/health")
        logger.info("=" * 60)

        if config.is_live:
            logger.warning("=" * 60)
            logger.warning("LIVE TRADING MODE ENABLED")
            logger.warning("Real money will be used. Proceed with caution!")
            logger.warning("=" * 60)

        logger.info("")
        logger.info("📡 Waiting for TradingView webhooks...")
        logger.info("")
        logger.info("Setup instructions:")
        logger.info("1. Start ngrok: ngrok http " + str(webhook_port))
        logger.info("2. Copy ngrok URL (e.g., https://abc123.ngrok.io)")
        logger.info("3. In TradingView alert, set webhook URL to:")
        logger.info("   https://your-ngrok-url.ngrok.io/tradingview/webhook")
        logger.info("")
        logger.info("See TRADINGVIEW_SETUP.md for detailed instructions")
        logger.info("=" * 60)

        # Start Flask server
        app.run(
            host='0.0.0.0',
            port=webhook_port,
            debug=False,
            threaded=True
        )

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
