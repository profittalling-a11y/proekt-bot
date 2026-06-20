"""Web API for dashboard."""
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import json
import logging
import time
from pathlib import Path
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../templates', static_folder='../static')
CORS(app)

# Connection persistence
_CONNECTIONS_FILE = Path("data/exchange_connections.json")

def _load_connections():
    """Load saved connections from file."""
    if _CONNECTIONS_FILE.exists():
        try:
            with open(_CONNECTIONS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_connections(connections):
    """Save connections to file."""
    _CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONNECTIONS_FILE, 'w') as f:
        json.dump(connections, f, indent=2)

def _save_to_env(exchange, api_key, api_secret, passphrase, testnet):
    """Save API credentials to .env file."""
    env_file = Path(".env")
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding='utf-8').splitlines()

    # Keys to update
    prefix = exchange.upper()
    new_keys = {
        f"{prefix}_API_KEY": api_key,
        f"{prefix}_API_SECRET": api_secret,
    }
    if passphrase:
        new_keys[f"{prefix}_PASSPHRASE"] = passphrase
    new_keys["EXCHANGE"] = exchange
    new_keys["TRADING_MODE"] = "testnet" if testnet else "live"

    # Update existing keys or append
    updated_keys = set()
    new_lines = []
    for line in lines:
        key = line.split("=")[0].strip() if "=" in line else ""
        if key in new_keys:
            new_lines.append(f"{key}={new_keys[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)

    # Append new keys
    for key, val in new_keys.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding='utf-8')

# Initialize connections from file
app._exchange_connections = _load_connections()

# Global state (thread-safe)
_state_lock = Lock()
_bot_state = {
    'balance': 0.0,
    'equity': 0.0,
    'open_positions': [],
    'statistics': {},
    'daily_pnl': [],
    'weekly_stats': {},
    'last_update': None,
    'is_running': False,
    'current_price': 0.0,
    'symbol': 'BTCUSDT',
    'exchange': 'okx',
    'timeframe': 15,
    'supertrend_multiplier': 3.0,
    'trading_pairs': [],
    'signals': [],
    'recent_trades': [],
}

# Bot control
_bot_instance = None
_config_instance = None
_account_manager = None
_multibot_manager = None


def set_bot_instance(bot):
    """Set bot instance for control.

    Args:
        bot: TradingBot instance
    """
    global _bot_instance
    _bot_instance = bot


def set_config_instance(config):
    """Set config instance for updates.

    Args:
        config: Config instance
    """
    global _config_instance
    _config_instance = config


def set_account_manager(manager):
    """Set account manager instance.

    Args:
        manager: AccountManager instance
    """
    global _account_manager
    _account_manager = manager


def set_multibot_manager(manager):
    """Set multibot manager instance.

    Args:
        manager: MultiBotManager instance
    """
    global _multibot_manager
    _multibot_manager = manager


def update_bot_state(
    balance: Optional[float] = None,
    equity: Optional[float] = None,
    open_positions: Optional[list] = None,
    statistics: Optional[dict] = None,
    daily_pnl: Optional[list] = None,
    weekly_stats: Optional[dict] = None,
    current_price: Optional[float] = None,
    symbol: Optional[str] = None,
    is_running: Optional[bool] = None,
    exchange: Optional[str] = None,
    timeframe: Optional[int] = None,
    supertrend_multiplier: Optional[float] = None,
    trading_pairs: Optional[list] = None,
    signals: Optional[list] = None,
    recent_trades: Optional[list] = None
):
    """Update bot state (called from trading bot).

    Args:
        balance: Current balance
        equity: Current equity
        open_positions: List of open positions
        statistics: Trading statistics
        daily_pnl: Daily PnL data
        weekly_stats: Weekly statistics
        current_price: Current market price
        symbol: Trading symbol
        is_running: Bot running status
        exchange: Exchange name
        timeframe: Timeframe in minutes
        supertrend_multiplier: Supertrend multiplier
        trading_pairs: List of trading pairs being analyzed
        signals: List of recent trading signals
        recent_trades: List of recent trades
    """
    with _state_lock:
        if balance is not None:
            _bot_state['balance'] = balance
        if equity is not None:
            _bot_state['equity'] = equity
        if open_positions is not None:
            _bot_state['open_positions'] = open_positions
        if statistics is not None:
            _bot_state['statistics'] = statistics
        if daily_pnl is not None:
            _bot_state['daily_pnl'] = daily_pnl
        if weekly_stats is not None:
            _bot_state['weekly_stats'] = weekly_stats
        if current_price is not None:
            _bot_state['current_price'] = current_price
        if symbol is not None:
            _bot_state['symbol'] = symbol
        if is_running is not None:
            _bot_state['is_running'] = is_running
        if exchange is not None:
            _bot_state['exchange'] = exchange
        if timeframe is not None:
            _bot_state['timeframe'] = timeframe
        if supertrend_multiplier is not None:
            _bot_state['supertrend_multiplier'] = supertrend_multiplier
        if trading_pairs is not None:
            _bot_state['trading_pairs'] = trading_pairs
        if signals is not None:
            _bot_state['signals'] = signals
        if recent_trades is not None:
            _bot_state['recent_trades'] = recent_trades

        from datetime import datetime
        _bot_state['last_update'] = datetime.now().isoformat()


def get_bot_state() -> dict:
    """Get current bot state.

    Returns:
        Bot state dictionary
    """
    with _state_lock:
        return _bot_state.copy()


@app.route('/')
def index():
    """Render dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """Get bot status.

    Returns:
        JSON with bot status
    """
    state = get_bot_state()
    return jsonify({
        'success': True,
        'data': {
            'is_running': state['is_running'],
            'symbol': state['symbol'],
            'current_price': state['current_price'],
            'balance': state['balance'],
            'equity': state['equity'],
            'last_update': state['last_update'],
        }
    })


@app.route('/api/positions')
def api_positions():
    """Get open positions.

    Returns:
        JSON with open positions
    """
    state = get_bot_state()
    return jsonify({
        'success': True,
        'data': state['open_positions']
    })


@app.route('/api/statistics')
def api_statistics():
    """Get trading statistics.

    Returns:
        JSON with statistics
    """
    state = get_bot_state()
    return jsonify({
        'success': True,
        'data': state['statistics']
    })


@app.route('/api/pnl')
def api_pnl():
    """Get daily PnL data.

    Returns:
        JSON with daily PnL
    """
    state = get_bot_state()
    return jsonify({
        'success': True,
        'data': state['daily_pnl']
    })


@app.route('/api/all')
def api_all():
    """Get all data at once.

    Returns:
        JSON with all bot data
    """
    state = get_bot_state()
    return jsonify({
        'success': True,
        'data': state
    })


@app.route('/api/control/start', methods=['POST'])
def api_start_bot():
    """Start the trading bot.

    Request JSON (optional):
        {
            "account_id": "account_id_to_start",
            "all_pairs": true  # Start bots for all pairs from leverage config
        }

    If account_id is provided, starts bot for that account.
    If all_pairs is true, starts bots for all trading pairs.
    If not provided, starts bot for active account (legacy mode).

    Returns:
        JSON with result
    """
    global _multibot_manager, _bot_instance

    data = request.get_json() or {}
    account_id = data.get('account_id')
    all_pairs = data.get('all_pairs', False)

    # Multi-bot mode with all pairs
    if _multibot_manager and account_id and all_pairs:
        try:
            result = _multibot_manager.start_bots_for_all_pairs(account_id)

            if result['success']:
                logger.info(f"Started {result['started']} bots for account: {account_id}")
                return jsonify({
                    'success': True,
                    'message': f"Started {result['started']} bots for {result['total']} pairs",
                    'started': result['started'],
                    'failed': result['failed'],
                    'total': result['total']
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Failed to start bots')
                }), 400

        except Exception as e:
            logger.error(f"Error starting bots for all pairs: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # Multi-bot mode (single pair)
    if _multibot_manager and account_id:
        try:
            success = _multibot_manager.start_bot(account_id)

            if success:
                logger.info(f"Bot started for account: {account_id}")
                return jsonify({
                    'success': True,
                    'message': 'Bot started successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to start bot'
                }), 400

        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # Legacy single-bot mode
    if _bot_instance is None:
        return jsonify({
            'success': False,
            'error': 'Bot instance not available'
        }), 400

    if _bot_instance.running:
        return jsonify({
            'success': False,
            'error': 'Bot is already running'
        }), 400

    try:
        # Start bot in background
        import threading
        bot_thread = threading.Thread(target=_bot_instance.start, daemon=True)
        bot_thread.start()

        logger.info("Bot started via dashboard")
        return jsonify({
            'success': True,
            'message': 'Bot started successfully'
        })
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/control/stop', methods=['POST'])
def api_stop_bot():
    """Stop the trading bot.

    Request JSON (optional):
        {
            "account_id": "account_id_to_stop"
        }

    If account_id is provided, stops bot for that account.
    If not provided, stops single bot (legacy mode).

    Returns:
        JSON with result
    """
    global _multibot_manager, _bot_instance

    data = request.get_json() or {}
    account_id = data.get('account_id')

    # Multi-bot mode
    if _multibot_manager and account_id:
        try:
            success = _multibot_manager.stop_bot(account_id)

            if success:
                logger.info(f"Bot stopped for account: {account_id}")
                return jsonify({
                    'success': True,
                    'message': 'Bot stopped successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Bot not found or not running'
                }), 400

        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # Legacy single-bot mode
    if _bot_instance is None:
        return jsonify({
            'success': False,
            'error': 'Bot instance not available'
        }), 400

    if not _bot_instance.running:
        return jsonify({
            'success': False,
            'error': 'Bot is not running'
        }), 400

    try:
        _bot_instance.stop()
        logger.info("Bot stopped via dashboard")
        return jsonify({
            'success': True,
            'message': 'Bot stopped successfully'
        })
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bots/running', methods=['GET'])
def api_get_running_bots():
    """Get list of all running bots.

    Returns:
        JSON with list of running bots
    """
    global _multibot_manager

    if _multibot_manager is None:
        return jsonify({
            'success': False,
            'error': 'Multi-bot manager not available'
        }), 400

    try:
        running_bots = _multibot_manager.get_running_bots()

        return jsonify({
            'success': True,
            'data': running_bots
        })

    except Exception as e:
        logger.error(f"Error getting running bots: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bots/start-all', methods=['POST'])
def api_start_all_bots():
    """Start bots for all accounts.

    Returns:
        JSON with result
    """
    global _multibot_manager, _account_manager

    if not _multibot_manager or not _account_manager:
        return jsonify({
            'success': False,
            'error': 'Managers not available'
        }), 400

    try:
        accounts = _account_manager.list_accounts()
        started = []
        failed = []

        for account in accounts:
            account_id = account['account_id']

            if _multibot_manager.is_bot_running(account_id):
                continue

            success = _multibot_manager.start_bot(account_id)

            if success:
                started.append(account['name'])
            else:
                failed.append(account['name'])

        return jsonify({
            'success': True,
            'message': f'Started {len(started)} bots',
            'data': {
                'started': started,
                'failed': failed
            }
        })

    except Exception as e:
        logger.error(f"Error starting all bots: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bots/stop-all', methods=['POST'])
def api_stop_all_bots():
    """Stop all running bots.

    Returns:
        JSON with result
    """
    global _multibot_manager

    if _multibot_manager is None:
        return jsonify({
            'success': False,
            'error': 'Multi-bot manager not available'
        }), 400

    try:
        _multibot_manager.stop_all_bots()

        logger.info("All bots stopped via dashboard")

        return jsonify({
            'success': True,
            'message': 'All bots stopped successfully'
        })

    except Exception as e:
        logger.error(f"Error stopping all bots: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/exchanges')
def api_exchanges():
    """Get list of supported exchanges.

    Returns:
        JSON with exchanges list
    """
    from .exchange_factory import ExchangeFactory

    exchanges = ExchangeFactory.get_supported_exchanges()
    return jsonify({
        'success': True,
        'data': exchanges
    })


@app.route('/api/exchange/connect', methods=['POST'])
def api_connect_exchange():
    """Connect to an exchange.

    Request JSON:
        {
            "exchange": "okx|bybit|bingx|gate|bitget|pionex|weex|toobit",
            "api_key": "...",
            "api_secret": "...",
            "passphrase": "..." (optional),
            "testnet": true|false
        }
    """
    try:
        data = request.get_json()
        exchange = data.get('exchange', '').lower()
        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')
        passphrase = data.get('passphrase', '')
        testnet = data.get('testnet', True)

        if not exchange or not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        from .exchange_factory import ExchangeFactory
        if exchange not in ExchangeFactory.get_supported_exchanges():
            return jsonify({'success': False, 'error': f'Unsupported exchange: {exchange}'}), 400

        # Store connection in module state
        if not hasattr(app, '_exchange_connections'):
            app._exchange_connections = {}

        app._exchange_connections[exchange] = {
            'api_key': api_key,
            'api_secret': api_secret,
            'passphrase': passphrase,
            'testnet': testnet
        }

        # Persist to file
        _save_connections(app._exchange_connections)

        # Save to .env file
        _save_to_env(exchange, api_key, api_secret, passphrase, testnet)

        logger.info(f"Exchange connected: {exchange} (testnet={testnet})")
        return jsonify({'success': True, 'message': f'{exchange} connected'})

    except Exception as e:
        logger.error(f"Error connecting exchange: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exchange/disconnect', methods=['POST'])
def api_disconnect_exchange():
    """Disconnect from an exchange."""
    try:
        data = request.get_json()
        exchange = data.get('exchange', '').lower()

        if hasattr(app, '_exchange_connections') and exchange in app._exchange_connections:
            del app._exchange_connections[exchange]
            _save_connections(app._exchange_connections)

        logger.info(f"Exchange disconnected: {exchange}")
        return jsonify({'success': True, 'message': f'{exchange} disconnected'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exchange/connections', methods=['GET'])
def api_get_connections():
    """Get all saved exchange connections (without secrets)."""
    try:
        connections = {}
        for ex, conn in app._exchange_connections.items():
            connections[ex] = {
                'exchange': ex,
                'testnet': conn.get('testnet', True),
                'has_key': bool(conn.get('api_key')),
            }
        return jsonify({'success': True, 'data': connections})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exchange/pairs', methods=['GET'])
def api_get_pairs():
    """Get trading pairs from connected exchange.

    Query params:
        exchange: Exchange name
    """
    try:
        exchange = request.args.get('exchange', '').lower()

        if not hasattr(app, '_exchange_connections') or exchange not in app._exchange_connections:
            return jsonify({'success': False, 'error': 'Exchange not connected'}), 400

        conn = app._exchange_connections[exchange]

        # Get exchange info to find available pairs
        try:
            # Try to get all instruments
            if exchange == 'okx':
                from okx.api import PublicData
                public = PublicData.PublicAPI(conn['api_key'], conn['api_secret'], conn.get('passphrase', ''), False, '1' if conn.get('testnet') else '0')
                resp = public.get_instruments(instType="SWAP")
                pairs = [inst['instId'] for inst in resp.get('data', []) if 'USDT' in inst.get('instId', '')]
            elif exchange == 'bybit':
                from pybit.unified_trading import HTTP
                session = HTTP(testnet=conn.get('testnet'), api_key=conn['api_key'], api_secret=conn['api_secret'])
                resp = session.get_instruments_info(category="linear")
                pairs = [inst['symbol'] for inst in resp.get('result', {}).get('list', []) if 'USDT' in inst.get('symbol', '')]
            elif exchange == 'gate':
                pairs = []  # Would need Gate API call
            elif exchange == 'bitget':
                pairs = []  # Would need Bitget API call
            else:
                pairs = []

            # Limit to 50 pairs
            pairs = sorted(pairs)[:50]

            return jsonify({'success': True, 'data': pairs})
        except Exception as e:
            logger.error(f"Error fetching pairs: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exchange/balance', methods=['GET'])
def api_get_balance():
    """Get balance from connected exchange.

    Query params:
        exchange: Exchange name
    """
    try:
        exchange = request.args.get('exchange', '').lower()

        if not hasattr(app, '_exchange_connections') or exchange not in app._exchange_connections:
            return jsonify({'success': False, 'error': 'Exchange not connected'}), 400

        conn = app._exchange_connections[exchange]
        from .exchange_factory import ExchangeFactory

        client = ExchangeFactory.create_client(
            exchange=exchange,
            api_key=conn['api_key'],
            api_secret=conn['api_secret'],
            passphrase=conn.get('passphrase', ''),
            testnet=conn.get('testnet', True)
        )

        balance = client.get_balance()
        return jsonify({'success': True, 'data': {'balance': balance, 'currency': 'USDT'}})

    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration."""
    global _config_instance
    if _config_instance is None:
        return jsonify({'success': False, 'error': 'Config not available'}), 400
    return jsonify({
        'success': True,
        'data': {
            'exchange': _config_instance.exchange.value,
            'timeframe': _config_instance.timeframe,
            'supertrend_multiplier': _config_instance.supertrend_multiplier,
            'atr_period': _config_instance.atr_period,
            'trading_mode': _config_instance.trading_mode.value,
            'webhook_port': getattr(_config_instance, 'webhook_port', 5001),
        }
    })


@app.route('/api/config/exchange', methods=['POST'])
def api_set_exchange():
    """Set exchange and API credentials.

    Request JSON:
        {
            "exchange": "okx|bybit|bingx",
            "api_key": "...",
            "api_secret": "...",
            "passphrase": "..." (optional, for OKX)
        }

    Returns:
        JSON with result
    """
    global _config_instance, _bot_instance

    if _config_instance is None:
        return jsonify({
            'success': False,
            'error': 'Config not available'
        }), 400

    if _bot_instance and _bot_instance.running:
        return jsonify({
            'success': False,
            'error': 'Cannot change exchange while bot is running'
        }), 400

    try:
        data = request.get_json()

        exchange = data.get('exchange', '').lower()
        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')
        passphrase = data.get('passphrase', '')

        if not exchange or not api_key or not api_secret:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        from .exchange_factory import ExchangeFactory

        if exchange not in ExchangeFactory.get_supported_exchanges():
            return jsonify({
                'success': False,
                'error': f'Unsupported exchange: {exchange}'
            }), 400

        if ExchangeFactory.requires_passphrase(exchange) and not passphrase:
            return jsonify({
                'success': False,
                'error': f'{exchange.upper()} requires passphrase'
            }), 400

        # Update config
        from .config import Exchange as ExchangeEnum
        _config_instance.exchange = ExchangeEnum(exchange)
        _config_instance.set_api_credentials(api_key, api_secret, passphrase)

        # Recreate bot instance with new exchange
        if _bot_instance:
            from .trader import TradingBot
            new_bot = TradingBot(_config_instance)
            set_bot_instance(new_bot)

        logger.info(f"Exchange changed to {exchange} via dashboard")

        return jsonify({
            'success': True,
            'message': f'Exchange set to {exchange}'
        })

    except Exception as e:
        logger.error(f"Error setting exchange: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/trading', methods=['POST'])
def api_set_trading_params():
    """Set trading parameters.

    Request JSON:
        {
            "timeframe": 5|10|15|30,
            "supertrend_multiplier": 1.0-10.0
        }

    Returns:
        JSON with result
    """
    global _config_instance, _bot_instance

    if _config_instance is None:
        return jsonify({
            'success': False,
            'error': 'Config not available'
        }), 400

    if _bot_instance and _bot_instance.running:
        return jsonify({
            'success': False,
            'error': 'Cannot change parameters while bot is running'
        }), 400

    try:
        data = request.get_json()

        timeframe = data.get('timeframe')
        supertrend_multiplier = data.get('supertrend_multiplier')

        if timeframe is not None:
            if timeframe not in [5, 10, 15, 30, 60, 120, 240]:
                return jsonify({
                    'success': False,
                    'error': 'Invalid timeframe. Must be 5, 10, 15, 30, 60, 120, or 240'
                }), 400
            _config_instance.timeframe = timeframe

        if supertrend_multiplier is not None:
            if not (1.0 <= supertrend_multiplier <= 10.0):
                return jsonify({
                    'success': False,
                    'error': 'Invalid multiplier. Must be between 1.0 and 10.0'
                }), 400
            _config_instance.supertrend_multiplier = supertrend_multiplier

        # Update bot state
        update_bot_state(
            timeframe=_config_instance.timeframe,
            supertrend_multiplier=_config_instance.supertrend_multiplier
        )

        logger.info(f"Trading params updated via dashboard: TF={timeframe}, ST={supertrend_multiplier}")

        return jsonify({
            'success': True,
            'message': 'Trading parameters updated'
        })

    except Exception as e:
        logger.error(f"Error setting trading params: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/accounts', methods=['GET'])
def api_list_accounts():
    """Get list of all accounts.

    Returns:
        JSON with accounts list
    """
    global _account_manager

    if _account_manager is None:
        return jsonify({
            'success': False,
            'error': 'Account manager not available'
        }), 400

    try:
        accounts = _account_manager.list_accounts()
        return jsonify({
            'success': True,
            'data': accounts
        })

    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/accounts', methods=['POST'])
def api_create_account():
    """Create new account.

    Request JSON:
        {
            "name": "My OKX Account",
            "exchange": "okx|bybit|bingx",
            "api_key": "...",
            "api_secret": "...",
            "passphrase": "..." (optional),
            "timeframe": 15,
            "supertrend_multiplier": 3.0,
            "trading_mode": "testnet|paper|live"
        }

    Returns:
        JSON with result
    """
    global _account_manager

    if _account_manager is None:
        return jsonify({
            'success': False,
            'error': 'Account manager not available'
        }), 400

    try:
        data = request.get_json()

        name = data.get('name', '').strip()
        exchange = data.get('exchange', '').lower()
        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')
        passphrase = data.get('passphrase', '')
        timeframe = data.get('timeframe', 15)
        supertrend_multiplier = data.get('supertrend_multiplier', 3.0)
        trading_mode = data.get('trading_mode', 'testnet')

        if not name or not exchange or not api_key or not api_secret:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        from .exchange_factory import ExchangeFactory

        if exchange not in ExchangeFactory.get_supported_exchanges():
            return jsonify({
                'success': False,
                'error': f'Unsupported exchange: {exchange}'
            }), 400

        if ExchangeFactory.requires_passphrase(exchange) and not passphrase:
            return jsonify({
                'success': False,
                'error': f'{exchange.upper()} requires passphrase'
            }), 400

        # Create account
        account = _account_manager.add_account(
            name=name,
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            timeframe=timeframe,
            supertrend_multiplier=supertrend_multiplier,
            trading_mode=trading_mode
        )

        logger.info(f"Account created: {name} ({exchange})")

        return jsonify({
            'success': True,
            'message': f'Account "{name}" created successfully',
            'data': {
                'account_id': account.account_id,
                'name': account.name,
                'exchange': account.exchange,
            }
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/accounts/<account_id>', methods=['DELETE'])
def api_delete_account(account_id: str):
    """Delete account.

    Args:
        account_id: Account ID to delete

    Returns:
        JSON with result
    """
    global _account_manager, _bot_instance

    if _account_manager is None:
        return jsonify({
            'success': False,
            'error': 'Account manager not available'
        }), 400

    if _bot_instance and _bot_instance.running:
        return jsonify({
            'success': False,
            'error': 'Cannot delete account while bot is running'
        }), 400

    try:
        success = _account_manager.remove_account(account_id)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Account not found'
            }), 404

        logger.info(f"Account deleted: {account_id}")

        return jsonify({
            'success': True,
            'message': 'Account deleted successfully'
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/accounts/<account_id>/activate', methods=['POST'])
def api_activate_account(account_id: str):
    """Activate account (switch to it).

    Args:
        account_id: Account ID to activate

    Returns:
        JSON with result
    """
    global _account_manager, _bot_instance, _config_instance

    if _account_manager is None:
        return jsonify({
            'success': False,
            'error': 'Account manager not available'
        }), 400

    if _bot_instance and _bot_instance.running:
        return jsonify({
            'success': False,
            'error': 'Cannot switch account while bot is running. Stop the bot first.'
        }), 400

    try:
        account = _account_manager.get_account(account_id)

        if not account:
            return jsonify({
                'success': False,
                'error': 'Account not found'
            }), 404

        # Set as active
        _account_manager.set_active_account(account_id)

        # Update config
        if _config_instance:
            from .config import Exchange as ExchangeEnum
            _config_instance.exchange = ExchangeEnum(account.exchange)
            _config_instance.set_api_credentials(
                account.api_key,
                account.api_secret,
                account.passphrase
            )
            _config_instance.timeframe = account.timeframe
            _config_instance.supertrend_multiplier = account.supertrend_multiplier
            _config_instance.trading_mode = account.trading_mode

            # Recreate bot instance
            if _bot_instance:
                from .trader import TradingBot
                new_bot = TradingBot(_config_instance)
                set_bot_instance(new_bot)

        # Update dashboard state
        update_bot_state(
            exchange=account.exchange,
            timeframe=account.timeframe,
            supertrend_multiplier=account.supertrend_multiplier
        )

        logger.info(f"Account activated: {account.name} ({account.exchange})")

        return jsonify({
            'success': True,
            'message': f'Switched to account "{account.name}"',
            'data': {
                'account_id': account.account_id,
                'name': account.name,
                'exchange': account.exchange,
                'timeframe': account.timeframe,
                'supertrend_multiplier': account.supertrend_multiplier,
            }
        })

    except Exception as e:
        logger.error(f"Error activating account: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/accounts/<account_id>', methods=['PATCH'])
def api_update_account(account_id: str):
    """Update account settings.

    Request JSON:
        {
            "name": "New Name" (optional),
            "timeframe": 15 (optional),
            "supertrend_multiplier": 3.0 (optional),
            "trading_mode": "testnet" (optional)
        }

    Returns:
        JSON with result
    """
    global _account_manager

    if _account_manager is None:
        return jsonify({
            'success': False,
            'error': 'Account manager not available'
        }), 400

    try:
        data = request.get_json()

        success = _account_manager.update_account(
            account_id=account_id,
            name=data.get('name'),
            timeframe=data.get('timeframe'),
            supertrend_multiplier=data.get('supertrend_multiplier'),
            trading_mode=data.get('trading_mode')
        )

        if not success:
            return jsonify({
                'success': False,
                'error': 'Account not found'
            }), 404

        logger.info(f"Account updated: {account_id}")

        return jsonify({
            'success': True,
            'message': 'Account updated successfully'
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/accounts/<account_id>/balance', methods=['GET'])
def api_get_account_balance(account_id: str):
    """Get balance for specific account.

    Args:
        account_id: Account ID

    Returns:
        JSON with balance info
    """
    global _account_manager

    if _account_manager is None:
        return jsonify({
            'success': False,
            'error': 'Account manager not available'
        }), 400

    try:
        account = _account_manager.get_account(account_id)

        if not account:
            return jsonify({
                'success': False,
                'error': 'Account not found'
            }), 404

        # Create exchange client
        from .exchange_factory import ExchangeFactory

        # Determine testnet mode
        is_testnet = (account.trading_mode == 'testnet')
        logger.info(f"Creating client for {account.name}: trading_mode={account.trading_mode}, is_testnet={is_testnet}")

        client = ExchangeFactory.create_client(
            exchange=account.exchange,
            api_key=account.api_key,
            api_secret=account.api_secret,
            passphrase=account.passphrase,
            testnet=is_testnet
        )

        # Get balance
        balance = client.get_balance()

        logger.info(f"Balance fetched for account {account.name}: {balance} USDT")

        return jsonify({
            'success': True,
            'data': {
                'balance': balance,
                'currency': 'USDT',
                'account_name': account.name,
                'exchange': account.exchange
            }
        })

    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/accounts/<account_id>/positions', methods=['GET'])
def api_get_account_positions(account_id: str):
    """Get open positions for specific account.

    Args:
        account_id: Account ID

    Returns:
        JSON with positions info
    """
    global _account_manager

    if _account_manager is None:
        return jsonify({
            'success': False,
            'error': 'Account manager not available'
        }), 400

    try:
        account = _account_manager.get_account(account_id)

        if not account:
            return jsonify({
                'success': False,
                'error': 'Account not found'
            }), 404

        # Create exchange client
        from .exchange_factory import ExchangeFactory

        is_testnet = (account.trading_mode == 'testnet')

        client = ExchangeFactory.create_client(
            exchange=account.exchange,
            api_key=account.api_key,
            api_secret=account.api_secret,
            passphrase=account.passphrase,
            testnet=is_testnet
        )

        # Get all positions - need to check multiple symbols
        positions = []

        # Get all open positions from exchange
        try:
            all_positions = client.get_all_positions()

            for position in all_positions:
                # Format position for dashboard
                direction = 'long' if position['side'] == 'Buy' else 'short'
                pnl = position.get('unrealized_pnl', 0)
                entry_price = position.get('entry_price', 0)
                size = position.get('size', 0)
                pnl_percent = (pnl / (entry_price * size) * 100) if (entry_price > 0 and size > 0) else 0

                positions.append({
                    'symbol': position.get('symbol', ''),
                    'direction': direction,
                    'size': size,
                    'entry_price': entry_price,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                    'leverage': position.get('leverage', 1)
                })
        except Exception as e:
            logger.warning(f"Error getting all positions: {e}")

        logger.info(f"Positions fetched for account {account.name}: {len(positions)} positions")

        return jsonify({
            'success': True,
            'data': {
                'positions': positions,
                'account_name': account.name,
                'exchange': account.exchange
            }
        })

    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/trading-pairs', methods=['GET'])
def api_get_trading_pairs():
    """Get all available trading pairs from config.

    Returns:
        JSON with list of trading pairs
    """
    try:
        if not _config_instance:
            return jsonify({
                'success': False,
                'error': 'Config not initialized'
            }), 500

        # Get pairs from leverage config string
        pairs = []
        if hasattr(_config_instance, 'leverage_config') and _config_instance.leverage_config:
            # Parse "BTCUSDT:50,ETHUSDT:50,..." format
            leverage_pairs = _config_instance.leverage_config.split(',')
            for pair in leverage_pairs:
                if ':' in pair:
                    symbol = pair.split(':')[0].strip()
                    pairs.append(symbol)

        return jsonify({
            'success': True,
            'data': {
                'pairs': pairs,
                'auto_scan': _config_instance.auto_scan if hasattr(_config_instance, 'auto_scan') else False
            }
        })

    except Exception as e:
        logger.error(f"Error fetching trading pairs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/multibot/start', methods=['POST'])
def api_multibot_start():
    """Start a bot for specific symbol.

    Request body:
        {
            "exchange": "okx",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": 15,
            "supertrend_multiplier": 3.0
        }
    """
    global _multibot_manager, _config_instance

    try:
        data = request.get_json()
        exchange = data.get('exchange', '')
        symbol = data.get('symbol', '')
        timeframe = data.get('timeframe', 15)
        multiplier = data.get('supertrend_multiplier', 3.0)

        if not exchange or not symbol:
            return jsonify({'success': False, 'error': 'exchange and symbol are required'}), 400

        # Get connection for this exchange
        conn = app._exchange_connections.get(exchange)
        if not conn:
            return jsonify({'success': False, 'error': f'{exchange} not connected'}), 400

        # Create config for this bot
        from .config import Config, Exchange as ExchangeEnum, TradingMode
        config = Config()
        config.exchange = ExchangeEnum(exchange)
        config.set_api_credentials(conn['api_key'], conn['api_secret'], conn.get('passphrase', ''))
        config.symbols = symbol
        config.timeframe = timeframe
        config.supertrend_multiplier = multiplier
        config.trading_mode = TradingMode('testnet' if conn.get('testnet', True) else 'live')

        # Normalize symbol for this exchange
        normalized = config.normalize_symbol(symbol)
        config.symbols = normalized
        logger.info(f"Bot symbol normalized: {symbol} -> {normalized} ({exchange})")

        # Create and start bot
        from .trader import TradingBot
        bot = TradingBot(config)
        import threading
        bot_id = f"{exchange}_{symbol}_{int(time.time()*1000)}"

        def start_bot_thread():
            bot.start()

        thread = threading.Thread(target=start_bot_thread, daemon=True)
        thread.start()

        logger.info(f"Bot started: {symbol} on {exchange}")
        return jsonify({'success': True, 'bot_id': bot_id, 'message': f'Bot started for {symbol}'})

    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/multibot/stop', methods=['POST'])
def api_multibot_stop():
    """Stop a specific bot.

    Request body:
        {
            "bot_id": "bot_id"
        }

    Returns:
        JSON with success status
    """
    global _multibot_manager

    if _multibot_manager is None:
        return jsonify({
            'success': False,
            'error': 'Multibot manager not available'
        }), 400

    try:
        data = request.get_json()
        bot_id = data.get('bot_id')

        if not bot_id:
            return jsonify({
                'success': False,
                'error': 'bot_id is required'
            }), 400

        # Stop bot through multibot manager
        _multibot_manager.stop_bot(bot_id)

        logger.info(f"Stopped bot {bot_id}")

        return jsonify({
            'success': True,
            'message': f'Bot {bot_id} stopped'
        })

    except Exception as e:
        logger.error(f"Error stopping multibot: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bot/<bot_id>/trend')
def api_bot_trend(bot_id: str):
    """Get trend information for a specific bot.

    Args:
        bot_id: Bot ID

    Returns:
        JSON with trend data
    """
    global _multibot_manager

    if not _multibot_manager:
        return jsonify({
            'success': False,
            'error': 'Multi-bot manager not initialized'
        }), 500

    try:
        # Get bot instance
        bot_instance = _multibot_manager.bots.get(bot_id)

        if not bot_instance:
            return jsonify({
                'success': False,
                'error': 'Bot not found'
            }), 404

        # Get trend data from bot
        bot = bot_instance.bot
        if not bot or not hasattr(bot, 'strategy'):
            return jsonify({
                'success': False,
                'error': 'Bot strategy not available'
            }), 500

        # Get current trend from strategy
        trend_direction = None
        trend_break = False

        if hasattr(bot.strategy, 'last_trend'):
            current_trend = bot.strategy.last_trend
            previous_trend = getattr(bot.strategy, 'previous_trend', None)

            # Detect trend break
            if previous_trend and current_trend != previous_trend:
                trend_break = True

            # Set direction
            if current_trend == 'bullish':
                trend_direction = 'BUY'
            elif current_trend == 'bearish':
                trend_direction = 'SELL'

        return jsonify({
            'success': True,
            'data': {
                'direction': trend_direction,
                'trend_break': trend_break,
                'symbol': bot_instance.symbol,
                'bot_id': bot_id
            }
        })

    except Exception as e:
        logger.error(f"Error getting trend for bot {bot_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/positions/all', methods=['GET'])
def api_get_all_positions():
    """Get all open positions from all running bots and accounts.

    Returns:
        JSON with all positions
    """
    try:
        all_positions = []

        # Get positions from running bots
        if _multibot_manager:
            for bot_instance in _multibot_manager.bots.values():
                if bot_instance.bot and bot_instance.is_running():
                    try:
                        position = bot_instance.bot.client.get_position(bot_instance.symbol)
                        if position:
                            position['account_name'] = bot_instance.account_name
                            position['bot_id'] = bot_instance.bot_id
                            all_positions.append(position)
                    except Exception as e:
                        logger.error(f"Error getting position for bot {bot_instance.bot_id}: {e}")

        # Also get positions from active account (including manual trades)
        if _account_manager:
            active_account = _account_manager.get_active_account()
            if active_account:
                try:
                    from .exchange_factory import ExchangeFactory
                    is_testnet = (active_account.trading_mode == 'testnet')

                    client = ExchangeFactory.create_client(
                        exchange=active_account.exchange,
                        api_key=active_account.api_key,
                        api_secret=active_account.api_secret,
                        passphrase=active_account.passphrase,
                        testnet=is_testnet
                    )

                    # Get all positions
                    positions = client.get_all_positions()
                    for pos in positions:
                        # Check if this position is already in the list from bots
                        if not any(p['symbol'] == pos['symbol'] for p in all_positions):
                            pos['account_name'] = active_account.name
                            pos['bot_id'] = 'manual'
                            all_positions.append(pos)

                except Exception as e:
                    logger.error(f"Error getting positions from active account: {e}")

        return jsonify({
            'success': True,
            'data': all_positions
        })

    except Exception as e:
        logger.error(f"Error fetching all positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/trades/history', methods=['GET'])
def api_get_trade_history():
    """Get trade history.

    Query params:
        limit: Maximum number of trades to return (default 50)
        status: Filter by status (open/closed)

    Returns:
        JSON with trade history
    """
    try:
        limit = int(request.args.get('limit', 50))
        status = request.args.get('status', 'closed')

        # Get trades from all running bots
        all_trades = []

        if _multibot_manager:
            for bot_instance in _multibot_manager.bots.values():
                if bot_instance.bot and hasattr(bot_instance.bot, 'trade_history'):
                    if status == 'closed':
                        trades = bot_instance.bot.trade_history.get_closed_trades(limit)
                    else:
                        trades = bot_instance.bot.trade_history.get_open_trades()

                    all_trades.extend([trade.to_dict() for trade in trades])

        # Sort by exit_time (for closed) or entry_time (for open)
        sort_key = 'exit_time' if status == 'closed' else 'entry_time'
        all_trades.sort(key=lambda x: x.get(sort_key, ''), reverse=True)

        return jsonify({
            'success': True,
            'data': all_trades[:limit]
        })

    except Exception as e:
        logger.error(f"Error fetching trade history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/hermes/signal', methods=['POST'])
def api_hermes_signal():
    """Receive signal from Hermes Agent.

    Request JSON:
        {
            "symbol": "BTCUSDT",
            "action": "buy" | "sell" | "close",
            "price": 50000.0,
            "confidence": 0.85,
            "source": "cumulative_delta"
        }
    """
    try:
        from .hermes_bridge import get_bridge, HermesSignal
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data'}), 400

        signal = HermesSignal(
            symbol=data.get('symbol', ''),
            action=data.get('action', ''),
            price=float(data.get('price', 0)),
            confidence=float(data.get('confidence', 0)),
            source=data.get('source', 'unknown')
        )

        bridge = get_bridge()
        result = bridge.receive_signal(signal)

        if result['accepted']:
            # Execute trade
            from .tradingview_webhook import _open_long, _open_short, _close_position
            if signal.action == 'buy':
                trade_result = _open_long(signal.symbol, signal.price)
            elif signal.action == 'sell':
                trade_result = _open_short(signal.symbol, signal.price)
            elif signal.action == 'close':
                trade_result = _close_position(signal.symbol)
            else:
                return jsonify({'success': False, 'error': f'Unknown action: {signal.action}'}), 400

            return jsonify({'success': True, 'signal': result, 'trade': trade_result}), 200
        else:
            return jsonify({'success': True, 'signal': result, 'trade': None}), 200

    except Exception as e:
        logger.error(f"Error processing Hermes signal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/hermes/status', methods=['GET'])
def api_hermes_status():
    """Get Hermes bridge status and statistics."""
    try:
        from .hermes_bridge import get_bridge
        bridge = get_bridge()
        return jsonify({
            'success': True,
            'data': {
                'stats': bridge.get_stats(),
                'recent_signals': bridge.get_recent_signals(10),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/agent/log', methods=['POST'])
def api_agent_log():
    """Log agent activity for dashboard display.

    Request JSON:
        {
            "agent": "signal" | "trade" | "system",
            "message": "BTC BUY @ 50000"
        }
    """
    try:
        data = request.get_json()
        agent = data.get('agent', 'system')
        message = data.get('message', '')
        logger.info(f"Agent [{agent}]: {message}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/agent/signals', methods=['GET'])
def api_agent_signals():
    """Get recent agent signals for dashboard display."""
    try:
        limit = int(request.args.get('limit', 50))
        signals = []
        if _multibot_manager:
            for bot_instance in _multibot_manager.bots.values():
                if bot_instance.bot and hasattr(bot_instance.bot, 'recent_signals'):
                    for sig in bot_instance.bot.recent_signals[-limit:]:
                        signals.append(sig)
        signals.sort(key=lambda x: x.get('time', ''), reverse=True)
        return jsonify({'success': True, 'data': signals[:limit]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def run_dashboard(host: str = '0.0.0.0', port: int = 80, debug: bool = False):
    """Run dashboard server with webhook on same port.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Debug mode
    """
    # Register webhook blueprint on same app
    try:
        from .tradingview_webhook import webhook_bp
        app.register_blueprint(webhook_bp)
        logger.info("Webhook blueprint registered on same port")
    except Exception as e:
        logger.warning(f"Could not register webhook blueprint: {e}")

    logger.info(f"Starting dashboard + webhook on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == '__main__':
    run_dashboard(debug=True)
