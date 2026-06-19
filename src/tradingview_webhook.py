"""TradingView Webhook Handler for automated trading."""
import logging
import hmac
import hashlib
from typing import Optional, Dict
from flask import Blueprint, request, jsonify

from .config import Config
from .exchange_factory import ExchangeFactory
from .risk_manager import RiskManager
from .telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)

# Blueprint for webhook routes
webhook_bp = Blueprint('webhook', __name__)

# Global instances (will be set from main)
_config: Optional[Config] = None
_client = None
_risk_manager: Optional[RiskManager] = None
_telegram: Optional[TelegramNotifier] = None

# Active positions tracking
_active_positions: Dict[str, Dict] = {}


def init_webhook_handler(config: Config):
    """Initialize webhook handler with config.

    Args:
        config: Bot configuration
    """
    global _config, _client, _risk_manager, _telegram

    _config = config

    # Initialize exchange client
    creds = config.get_api_credentials()
    _client = ExchangeFactory.create_client(
        exchange=config.exchange.value,
        api_key=creds.get("api_key", ""),
        api_secret=creds.get("api_secret", ""),
        passphrase=creds.get("passphrase", ""),
        testnet=config.is_testnet
    )

    # Initialize risk manager
    _risk_manager = RiskManager(
        fixed_position_size=config.fixed_position_size,
        risk_per_position=config.risk_per_position,
        max_positions=config.max_positions,
        max_daily_loss=config.max_daily_loss,
        cooldown_after_loss=config.cooldown_after_loss,
        min_balance=config.min_balance
    )

    # Initialize telegram
    _telegram = TelegramNotifier(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        enabled=config.telegram_enabled
    )

    logger.info("TradingView webhook handler initialized")


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature for security.

    Args:
        payload: Request payload
        signature: Signature from header
        secret: Webhook secret key

    Returns:
        True if signature is valid
    """
    if not secret:
        return True  # Skip verification if no secret configured

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@webhook_bp.route('/tradingview/webhook', methods=['POST'])
def tradingview_webhook():
    """Handle TradingView webhook alerts.

    Expected JSON payload:
    {
        "symbol": "BTCUSDT",
        "action": "buy" or "sell" or "close",
        "price": 50000.0,
        "stop_loss": 49000.0,
        "take_profit": 52000.0  (optional)
    }
    """
    try:
        # Verify signature if configured
        webhook_secret = getattr(_config, 'tradingview_webhook_secret', '')
        if webhook_secret:
            signature = request.headers.get('X-Signature', '')
            if not verify_signature(request.data, signature, webhook_secret):
                logger.warning("Invalid webhook signature")
                return jsonify({'error': 'Invalid signature'}), 401

        # Parse webhook data
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        symbol = data.get('symbol', '').upper()
        action = data.get('action', '').lower()
        price = float(data.get('price', 0))
        stop_loss = data.get('stop_loss')
        take_profit = data.get('take_profit')

        # Validate data
        if not symbol or not action:
            return jsonify({'error': 'Missing symbol or action'}), 400

        # Normalize symbol to exchange format
        symbol = _normalize_symbol(symbol)

        logger.info(f"TradingView webhook: {action.upper()} {symbol} @ {price}")

        # Execute action
        if action == 'buy':
            result = _open_long(symbol, price, stop_loss, take_profit)
        elif action == 'sell':
            result = _open_short(symbol, price, stop_loss, take_profit)
        elif action == 'close':
            result = _close_position(symbol)
        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _normalize_symbol(symbol: str) -> str:
    """Normalize symbol to exchange format.

    Args:
        symbol: Symbol from TradingView (e.g., BTCUSDT)

    Returns:
        Normalized symbol (e.g., BTC-USDT-SWAP for OKX)
    """
    # Remove common suffixes
    symbol = symbol.replace('PERP', '').replace('USD', '')

    if _config.exchange.value == "okx":
        # Convert BTCUSDT to BTC-USDT-SWAP
        if 'USDT' in symbol:
            base = symbol.replace('USDT', '')
            return f"{base}-USDT-SWAP"
        else:
            return f"{symbol}-USDT-SWAP"
    elif _config.exchange.value == "bybit":
        # Bybit format: BTCUSDT
        if not symbol.endswith('USDT'):
            return f"{symbol}USDT"
        return symbol
    elif _config.exchange.value == "bingx":
        # BingX format: BTC-USDT
        if '-' not in symbol and 'USDT' in symbol:
            base = symbol.replace('USDT', '')
            return f"{base}-USDT"
        return symbol

    return symbol


def _open_long(symbol: str, entry_price: float, stop_loss: Optional[float], take_profit: Optional[float]) -> Dict:
    """Open long position.

    Args:
        symbol: Trading symbol
        entry_price: Entry price
        stop_loss: Stop loss price (optional)
        take_profit: Take profit price (optional)

    Returns:
        Result dictionary
    """
    try:
        # Check if already have position
        if symbol in _active_positions:
            return {'success': False, 'message': f'Already have position on {symbol}'}

        # Get balance
        balance = _client.get_balance()

        # Check risk management
        can_trade, reason = _risk_manager.can_trade(balance, symbol=symbol)
        if not can_trade:
            logger.warning(f"Trading not allowed: {reason}")
            return {'success': False, 'message': reason}

        # Calculate stop loss if not provided
        if not stop_loss:
            # Use 2% from entry as default
            stop_loss = entry_price * 0.98

        # Get leverage for symbol
        leverage = _config.get_leverage_for_symbol(symbol)

        # Calculate position size
        position_size_usdt = _risk_manager.calculate_position_size(
            balance=balance,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage
        )

        # Convert to quantity
        qty = position_size_usdt / entry_price

        # Validate order
        is_valid, reason = _risk_manager.validate_order(balance, position_size_usdt, entry_price)
        if not is_valid:
            logger.error(f"Order validation failed: {reason}")
            return {'success': False, 'message': reason}

        logger.info(
            f"Opening LONG: {symbol}, qty={qty:.4f}, entry={entry_price:.2f}, "
            f"SL={stop_loss:.2f}, TP={take_profit if take_profit else 'None'}"
        )

        # Place order
        _client.place_order(
            symbol=symbol,
            side='Buy',
            qty=qty,
            order_type='Market',
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Track position
        _active_positions[symbol] = {
            'side': 'Buy',
            'qty': qty,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }

        # Send Telegram notification
        _telegram.notify_position_opened(
            symbol=symbol,
            direction='LONG',
            entry_price=entry_price,
            quantity=qty,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        logger.info(f"LONG position opened: {symbol}")

        return {
            'success': True,
            'message': f'LONG position opened on {symbol}',
            'qty': qty,
            'entry_price': entry_price,
            'stop_loss': stop_loss
        }

    except Exception as e:
        logger.error(f"Error opening LONG: {e}", exc_info=True)
        return {'success': False, 'message': str(e)}


def _open_short(symbol: str, entry_price: float, stop_loss: Optional[float], take_profit: Optional[float]) -> Dict:
    """Open short position.

    Args:
        symbol: Trading symbol
        entry_price: Entry price
        stop_loss: Stop loss price (optional)
        take_profit: Take profit price (optional)

    Returns:
        Result dictionary
    """
    try:
        # Check if already have position
        if symbol in _active_positions:
            return {'success': False, 'message': f'Already have position on {symbol}'}

        # Get balance
        balance = _client.get_balance()

        # Check risk management
        can_trade, reason = _risk_manager.can_trade(balance, symbol=symbol)
        if not can_trade:
            logger.warning(f"Trading not allowed: {reason}")
            return {'success': False, 'message': reason}

        # Calculate stop loss if not provided
        if not stop_loss:
            # Use 2% from entry as default
            stop_loss = entry_price * 1.02

        # Get leverage for symbol
        leverage = _config.get_leverage_for_symbol(symbol)

        # Calculate position size
        position_size_usdt = _risk_manager.calculate_position_size(
            balance=balance,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage
        )

        # Convert to quantity
        qty = position_size_usdt / entry_price

        # Validate order
        is_valid, reason = _risk_manager.validate_order(balance, position_size_usdt, entry_price)
        if not is_valid:
            logger.error(f"Order validation failed: {reason}")
            return {'success': False, 'message': reason}

        logger.info(
            f"Opening SHORT: {symbol}, qty={qty:.4f}, entry={entry_price:.2f}, "
            f"SL={stop_loss:.2f}, TP={take_profit if take_profit else 'None'}"
        )

        # Place order
        _client.place_order(
            symbol=symbol,
            side='Sell',
            qty=qty,
            order_type='Market',
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Track position
        _active_positions[symbol] = {
            'side': 'Sell',
            'qty': qty,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }

        # Send Telegram notification
        _telegram.notify_position_opened(
            symbol=symbol,
            direction='SHORT',
            entry_price=entry_price,
            quantity=qty,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        logger.info(f"SHORT position opened: {symbol}")

        return {
            'success': True,
            'message': f'SHORT position opened on {symbol}',
            'qty': qty,
            'entry_price': entry_price,
            'stop_loss': stop_loss
        }

    except Exception as e:
        logger.error(f"Error opening SHORT: {e}", exc_info=True)
        return {'success': False, 'message': str(e)}


def _close_position(symbol: str) -> Dict:
    """Close position for symbol.

    Args:
        symbol: Trading symbol

    Returns:
        Result dictionary
    """
    try:
        # Check if have position
        if symbol not in _active_positions:
            # Try to get from exchange
            position = _client.get_position(symbol)
            if not position:
                return {'success': False, 'message': f'No position found for {symbol}'}
        else:
            position = _active_positions[symbol]

        logger.info(f"Closing position: {symbol}")

        # Close position
        _client.close_position(
            symbol=symbol,
            side=position['side'],
            qty=position['qty']
        )

        # Get final position info for PnL
        final_position = _client.get_position(symbol)
        pnl = final_position.get('unrealized_pnl', 0) if final_position else 0

        # Record trade
        _risk_manager.record_trade(pnl, symbol=symbol)

        # Remove from active positions
        if symbol in _active_positions:
            del _active_positions[symbol]

        # Send Telegram notification
        direction = 'LONG' if position['side'] == 'Buy' else 'SHORT'
        _telegram.notify_position_closed(
            symbol=symbol,
            direction=direction,
            entry_price=position.get('entry_price', 0),
            exit_price=0,  # Will be filled by exchange
            quantity=position['qty'],
            pnl=pnl,
            pnl_percent=0,
            reason='TradingView signal'
        )

        logger.info(f"Position closed: {symbol}, PnL: {pnl:.2f} USDT")

        return {
            'success': True,
            'message': f'Position closed on {symbol}',
            'pnl': pnl
        }

    except Exception as e:
        logger.error(f"Error closing position: {e}", exc_info=True)
        return {'success': False, 'message': str(e)}
