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

webhook_bp = Blueprint('webhook', __name__)

_config: Optional[Config] = None
_client = None
_risk_manager: Optional[RiskManager] = None
_telegram: Optional[TelegramNotifier] = None

_active_positions: Dict[str, Dict] = {}
_trend_state: Dict[str, str] = {}


def init_webhook_handler(config: Config):
    global _config, _client, _risk_manager, _telegram
    _config = config
    creds = config.get_api_credentials()
    _client = ExchangeFactory.create_client(
        exchange=config.exchange.value,
        api_key=creds.get("api_key", ""),
        api_secret=creds.get("api_secret", ""),
        passphrase=creds.get("passphrase", ""),
        testnet=config.is_testnet
    )
    _risk_manager = RiskManager(
        fixed_position_size=config.fixed_position_size,
        risk_per_position=config.risk_per_position,
        max_positions=config.max_positions,
        max_daily_loss=config.max_daily_loss,
        cooldown_after_loss=config.cooldown_after_loss,
        min_balance=config.min_balance
    )
    _telegram = TelegramNotifier(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        enabled=config.telegram_enabled
    )
    logger.info("TradingView webhook handler initialized")


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not secret:
        return True
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


@webhook_bp.route('/tradingview/webhook', methods=['POST'])
def tradingview_webhook():
    """Handle TradingView webhook alerts.

    Expected JSON payload:
    {
        "symbol": "BTCUSDT",
        "action": "buy" or "sell",
        "price": 50000.0
    }
    """
    try:
        webhook_secret = getattr(_config, 'tradingview_webhook_secret', '')
        if webhook_secret:
            signature = request.headers.get('X-Signature', '')
            if not verify_signature(request.data, signature, webhook_secret):
                logger.warning("Invalid webhook signature")
                return jsonify({'error': 'Invalid signature'}), 401

        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        symbol = data.get('symbol', '').upper()
        action = data.get('action', '').lower()
        price = float(data.get('price', 0))

        if not symbol or not action:
            return jsonify({'error': 'Missing symbol or action'}), 400

        symbol = _normalize_symbol(symbol)
        logger.info(f"TradingView webhook: {action.upper()} {symbol} @ {price}")

        # Trend change detection - skip false signals
        if not _is_valid_trend_signal(symbol, action):
            logger.info(f"Skipping false signal: {action.upper()} {symbol} (no trend change)")
            return jsonify({'success': True, 'message': 'Signal skipped (no trend change)'}), 200

        if action == 'buy':
            result = _open_long(symbol, price)
        elif action == 'sell':
            result = _open_short(symbol, price)
        elif action == 'close':
            result = _close_position(symbol)
        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _is_valid_trend_signal(symbol: str, action: str) -> bool:
    """Check if signal represents a real trend change.

    Skips signals that don't represent a trend reversal:
    - If current trend is 'buy' and new signal is 'buy' -> skip
    - If current trend is 'sell' and new signal is 'sell' -> skip
    - Only process when trend actually changes direction
    """
    current_trend = _trend_state.get(symbol)

    if current_trend is None:
        # First signal for this symbol - always valid
        _trend_state[symbol] = action
        return True

    if current_trend == action:
        # Same direction as current trend - false signal, skip
        return False

    # Trend changed - valid signal
    _trend_state[symbol] = action
    return True


def _normalize_symbol(symbol: str) -> str:
    if _config.exchange.value == "okx":
        if 'USDT' in symbol:
            base = symbol.replace('USDT', '').replace('-', '')
            return f"{base}-USDT-SWAP"
        return f"{symbol}-USDT-SWAP"
    elif _config.exchange.value == "bybit":
        if not symbol.endswith('USDT'):
            return f"{symbol}USDT"
        return symbol
    elif _config.exchange.value == "bingx":
        if '-' not in symbol and 'USDT' in symbol:
            base = symbol.replace('USDT', '')
            return f"{base}-USDT"
        return symbol
    return symbol


def _open_long(symbol: str, entry_price: float) -> Dict:
    """Open long position. NO STOP LOSS - exit by signal only."""
    try:
        if symbol in _active_positions:
            return {'success': False, 'message': f'Already have position on {symbol}'}

        balance = _client.get_balance()
        can_trade, reason = _risk_manager.can_trade(balance, symbol=symbol)
        if not can_trade:
            return {'success': False, 'message': reason}

        leverage = _config.get_leverage_for_symbol(symbol)
        position_size_usdt = _risk_manager.calculate_position_size(
            balance=balance, entry_price=entry_price,
            stop_loss=entry_price * 0.95, leverage=leverage
        )
        qty = position_size_usdt / entry_price

        is_valid, reason = _risk_manager.validate_order(balance, position_size_usdt, entry_price)
        if not is_valid:
            return {'success': False, 'message': reason}

        logger.info(f"Opening LONG: {symbol}, qty={qty:.4f}, entry={entry_price:.2f} (NO STOP LOSS)")

        _client.place_order(
            symbol=symbol, side='Buy', qty=qty, order_type='Market',
            stop_loss=None, take_profit=None
        )

        _active_positions[symbol] = {
            'side': 'Buy', 'qty': qty, 'entry_price': entry_price
        }

        _telegram.notify_position_opened(
            symbol=symbol, direction='LONG', entry_price=entry_price,
            quantity=qty, leverage=leverage, stop_loss=None, take_profit=None
        )

        return {
            'success': True, 'message': f'LONG opened on {symbol}',
            'qty': qty, 'entry_price': entry_price
        }
    except Exception as e:
        logger.error(f"Error opening LONG: {e}", exc_info=True)
        return {'success': False, 'message': str(e)}


def _open_short(symbol: str, entry_price: float) -> Dict:
    """Open short position. NO STOP LOSS - exit by signal only."""
    try:
        if symbol in _active_positions:
            return {'success': False, 'message': f'Already have position on {symbol}'}

        balance = _client.get_balance()
        can_trade, reason = _risk_manager.can_trade(balance, symbol=symbol)
        if not can_trade:
            return {'success': False, 'message': reason}

        leverage = _config.get_leverage_for_symbol(symbol)
        position_size_usdt = _risk_manager.calculate_position_size(
            balance=balance, entry_price=entry_price,
            stop_loss=entry_price * 1.05, leverage=leverage
        )
        qty = position_size_usdt / entry_price

        is_valid, reason = _risk_manager.validate_order(balance, position_size_usdt, entry_price)
        if not is_valid:
            return {'success': False, 'message': reason}

        logger.info(f"Opening SHORT: {symbol}, qty={qty:.4f}, entry={entry_price:.2f} (NO STOP LOSS)")

        _client.place_order(
            symbol=symbol, side='Sell', qty=qty, order_type='Market',
            stop_loss=None, take_profit=None
        )

        _active_positions[symbol] = {
            'side': 'Sell', 'qty': qty, 'entry_price': entry_price
        }

        _telegram.notify_position_opened(
            symbol=symbol, direction='SHORT', entry_price=entry_price,
            quantity=qty, leverage=leverage, stop_loss=None, take_profit=None
        )

        return {
            'success': True, 'message': f'SHORT opened on {symbol}',
            'qty': qty, 'entry_price': entry_price
        }
    except Exception as e:
        logger.error(f"Error opening SHORT: {e}", exc_info=True)
        return {'success': False, 'message': str(e)}


def _close_position(symbol: str) -> Dict:
    try:
        if symbol not in _active_positions:
            position = _client.get_position(symbol)
            if not position:
                return {'success': False, 'message': f'No position for {symbol}'}
            pos_data = position
        else:
            pos_data = _active_positions[symbol]

        _client.close_position(symbol=symbol, side=pos_data['side'], qty=pos_data['qty'])

        pnl = 0
        try:
            final_pos = _client.get_position(symbol)
            if final_pos:
                pnl = final_pos.get('unrealized_pnl', 0)
        except Exception:
            pass

        _risk_manager.record_trade(pnl, symbol=symbol)

        if symbol in _active_positions:
            del _active_positions[symbol]

        _telegram.notify_position_closed(
            symbol=symbol,
            direction='LONG' if pos_data['side'] == 'Buy' else 'SHORT',
            entry_price=pos_data.get('entry_price', 0),
            exit_price=0, quantity=pos_data['qty'],
            pnl=pnl, pnl_percent=0, reason='TradingView signal'
        )

        return {'success': True, 'message': f'Position closed on {symbol}', 'pnl': pnl}
    except Exception as e:
        logger.error(f"Error closing position: {e}", exc_info=True)
        return {'success': False, 'message': str(e)}
