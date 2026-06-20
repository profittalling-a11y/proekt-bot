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


@webhook_bp.route('/tradingview/webhook', methods=['GET', 'POST'])
def tradingview_webhook():
    """Handle TradingView webhook alerts.

    Expected JSON payload:
    {
        "symbol": "BTCUSDT",
        "action": "buy" or "sell",
        "price": 50000.0
    }
    """
    # Handle GET requests (ngrok browser check, health check)
    if request.method == 'GET':
        return jsonify({'status': 'ok', 'message': 'Webhook endpoint ready'}), 200
    try:
        # Accept any request - log everything
        raw_data = request.get_data(as_text=True).strip()
        logger.info(f"Webhook received: {request.method} {request.remote_addr} data={raw_data[:500]}")

        # Try to parse JSON
        data = None
        if raw_data:
            try:
                import json
                data = json.loads(raw_data)
            except Exception:
                data = None

        symbol = ''
        action = ''
        price = 0.0

        if data and isinstance(data, dict):
            # JSON format: {"symbol":"SOLUSDT","action":"sell","price":73.15}
            symbol = data.get('symbol', '').upper()
            action = data.get('action', '').lower()
            price = float(data.get('price', 0))
        elif raw_data:
            # Plain text format: "SuperTrend Buy!" or "SuperTrend Sell!"
            text = raw_data.upper()
            if 'BUY' in text or 'LONG' in text:
                action = 'buy'
            elif 'SELL' in text or 'SHORT' in text:
                action = 'sell'
            elif 'CLOSE' in text:
                action = 'close'

            # Try to extract symbol from text
            import re
            symbols_found = re.findall(r'[A-Z]{2,10}USDT', text)
            if symbols_found:
                symbol = symbols_found[0]
            else:
                symbol = 'SOLUSDT'  # Default

        if not action:
            return jsonify({'success': True, 'message': 'Received', 'raw': raw_data[:200]}), 200

        logger.info(f"TradingView signal: {action.upper()} {symbol} @ {price}")

        logger.info(f"TradingView webhook received: {action.upper()} {symbol} @ {price}")

        # Store signal in file for dashboard to read
        from pathlib import Path
        import json
        import time

        signals_file = Path("data/tradingview_signals.json")
        signals_file.parent.mkdir(parents=True, exist_ok=True)

        signals = []
        if signals_file.exists():
            try:
                signals = json.loads(signals_file.read_text(encoding='utf-8'))
            except Exception:
                signals = []

        signals.append({
            'symbol': symbol,
            'action': action,
            'price': price,
            'timestamp': time.time(),
            'time': time.strftime('%H:%M:%S')
        })

        # Keep last 50 signals
        signals = signals[-50:]
        signals_file.write_text(json.dumps(signals, indent=2), encoding='utf-8')

        # If no config, just log and return
        if _config is None:
            logger.warning("No exchange configured - signal logged but not executed")
            return jsonify({
                'success': True,
                'message': f'Signal logged: {action.upper()} {symbol} @ {price}',
                'executed': False,
                'reason': 'No exchange connected'
            }), 200

        if not symbol or not action:
            return jsonify({'error': 'Missing symbol or action'}), 400

        symbol = _normalize_symbol(symbol)
        logger.info(f"TradingView webhook: {action.upper()} {symbol} @ {price}")

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
