"""Main trading bot engine."""
import logging
import time
from typing import Optional
from datetime import datetime
import uuid

from .config import Config
from .exchange_factory import ExchangeFactory
from .indicators import IndicatorCalculator
from .strategy import SupertrendStrategy, Signal
from .risk_manager import RiskManager
from .trade_history import TradeHistory
from .telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot orchestrator."""

    def __init__(self, config: Config):
        """Initialize trading bot.

        Args:
            config: Bot configuration
        """
        self.config = config
        self.running = False

        # Normalize symbol for the selected exchange
        self.config.symbols = config.normalize_symbol(config.symbols)
        logger.info(f"Normalized symbol to {config.exchange.value} format: {self.config.symbols}")

        # Initialize components
        creds = config.get_api_credentials()

        self.client = ExchangeFactory.create_client(
            exchange=config.exchange.value,
            api_key=creds.get("api_key", ""),
            api_secret=creds.get("api_secret", ""),
            passphrase=creds.get("passphrase", ""),
            testnet=config.is_testnet
        )

        self.strategy = SupertrendStrategy(
            use_ema_filter=config.use_ema_filter,
            ema_period=config.ema_period,
            use_volume_filter=config.use_volume_filter,
            min_volume_multiplier=config.min_volume_multiplier
        )

        self.risk_manager = RiskManager(
            fixed_position_size=config.fixed_position_size,
            risk_per_position=config.risk_per_position,
            max_positions=config.max_positions,
            max_daily_loss=config.max_daily_loss,
            cooldown_after_loss=config.cooldown_after_loss,
            min_balance=config.min_balance
        )

        self.indicator_calculator = IndicatorCalculator()

        # Trade history
        self.trade_history = TradeHistory()

        # Telegram notifier
        self.telegram = TelegramNotifier(
            bot_token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            enabled=config.telegram_enabled
        )

        # State tracking
        self.last_candle_time = None
        self.position_entry_price = None
        self.current_trade_id = None
        self.current_price = 0.0

        # Dashboard tracking
        self.recent_signals = []  # Store last 10 signals
        self.recent_trades = []   # Store last 10 completed trades
        self.max_recent_items = 10

        logger.info(f"Trading bot initialized for {config.symbol}")

    def start(self):
        """Start the trading bot."""
        # CRITICAL: Log immediately to verify method is called
        logger.critical(f"!!! BOT START METHOD CALLED FOR {self.config.symbol} !!!")

        # Validate symbol format before starting
        try:
            logger.info(f"Validating symbol: {self.config.symbol}")
            # Try to get exchange info to validate symbol exists
            exchange_info = self.client.get_exchange_info(self.config.symbol)
            if exchange_info:
                logger.info(f"Symbol validated: {self.config.symbol}")
                logger.info(f"Min qty: {exchange_info.get('min_qty', 'N/A')}, Max leverage: {exchange_info.get('max_leverage', 'N/A')}")
            else:
                logger.warning(f"Could not validate symbol {self.config.symbol}, proceeding anyway")
        except Exception as e:
            logger.error(f"Symbol validation failed: {e}")
            logger.error(f"Please check if {self.config.symbol} is a valid trading pair on {self.config.exchange.value.upper()}")
            raise ValueError(f"Invalid symbol: {self.config.symbol}. Error: {e}")

        self.running = True
        logger.info("=" * 60)
        logger.info("TRADING BOT STARTED")
        logger.info(f"Exchange: {self.config.exchange.value.upper()}")
        logger.info(f"Mode: {self.config.trading_mode.value.upper()}")
        logger.info(f"Symbol: {self.config.symbol}")
        logger.info(f"Timeframe: {self.config.timeframe}m")
        logger.info(f"Supertrend: ATR={self.config.atr_period}, Multiplier={self.config.supertrend_multiplier}")
        logger.info("=" * 60)

        # Update dashboard status
        from .dashboard_api import update_bot_state
        update_bot_state(
            is_running=True,
            symbol=self.config.symbol,
            trading_pairs=[self.config.symbol],
            timeframe=self.config.timeframe,
            supertrend_multiplier=self.config.supertrend_multiplier
        )

        # Send Telegram notification
        self.telegram.notify_bot_started()

        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.stop()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.telegram.notify_error(f"Fatal error: {str(e)}")
            self.stop()

    def stop(self):
        """Stop the trading bot."""
        self.running = False
        logger.info("Trading bot stopped")

        # Update dashboard status
        from .dashboard_api import update_bot_state
        update_bot_state(is_running=False)

        self.telegram.notify_bot_stopped()
        self._print_summary()

    def _run_loop(self):
        """Main trading loop."""
        while self.running:
            try:
                self._execute_cycle()
                time.sleep(self.config.polling_interval)

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    logger.warning("Rate limit exceeded (429), waiting 60 seconds...")
                    time.sleep(60)
                else:
                    logger.error(f"Error in trading cycle: {e}", exc_info=True)
                    time.sleep(self.config.polling_interval)

    def _execute_cycle(self):
        """Execute one trading cycle."""
        # Get current position and balance first (update dashboard every cycle)
        position = self.client.get_position(self.config.symbol)
        balance = self.client.get_balance()

        # Get latest klines
        interval = self._get_interval_string()
        klines = self.client.get_klines(
            symbol=self.config.symbol,
            interval=interval,
            limit=200
        )

        if not klines or len(klines) < self.config.atr_period + 10:
            logger.warning("Insufficient kline data")
            # Still update dashboard with current balance/position
            self._update_dashboard_state(balance, position)
            return

        # Update current price from latest candle
        self.current_price = klines[-1]['close']

        # Update dashboard with current data
        self._update_dashboard_state(balance, position)

        # Check if new candle closed
        latest_candle_time = klines[-1]['timestamp']
        if self.last_candle_time == latest_candle_time:
            return  # Same candle, wait for next

        self.last_candle_time = latest_candle_time
        logger.info(f"New candle closed at {datetime.fromtimestamp(latest_candle_time/1000)}")
        logger.info(f"Balance: {balance:.2f} USDT")

        # Calculate indicators
        df = self.indicator_calculator.calculate_all_indicators(
            klines,
            atr_period=self.config.atr_period,
            supertrend_multiplier=self.config.supertrend_multiplier,
            ema_period=self.config.ema_period,
            volume_period=20
        )

        signal_data = self.indicator_calculator.get_latest_signal(df)

        # Check risk management
        current_positions = 1 if position else 0
        can_trade, reason = self.risk_manager.can_trade(
            balance=balance,
            symbol=self.config.symbol,
            current_positions=current_positions
        )
        if not can_trade:
            logger.warning(f"Trading not allowed: {reason}")
            return

        # Generate signal
        signal = self.strategy.generate_signal(signal_data, position)

        # Execute signal
        if signal != Signal.HOLD:
            self._execute_signal(signal, signal_data, position, balance)

        # Print status
        self._print_status(signal_data, position, balance)

    def _execute_signal(
        self,
        signal: Signal,
        signal_data: dict,
        position: Optional[dict],
        balance: float
    ):
        """Execute trading signal.

        Args:
            signal: Trading signal
            signal_data: Signal data with indicators
            position: Current position
            balance: Account balance
        """
        if self.config.is_paper_trading:
            logger.info(f"[PAPER TRADING] Signal: {signal.value}")
            return

        try:
            if signal == Signal.CLOSE_LONG or signal == Signal.CLOSE_SHORT:
                self._close_position(position)

            elif signal == Signal.LONG:
                self._open_long(signal_data, balance)

            elif signal == Signal.SHORT:
                self._open_short(signal_data, balance)

        except Exception as e:
            logger.error(f"Error executing signal: {e}", exc_info=True)

    def _open_long(self, signal_data: dict, balance: float):
        """Open long position.

        Args:
            signal_data: Signal data
            balance: Account balance
        """
        entry_price = signal_data['close']
        supertrend = signal_data['supertrend']
        atr = signal_data['atr']
        swing_low = signal_data.get('swing_low')

        # Calculate stop loss using swing low
        stop_loss = self.strategy.calculate_stop_loss(
            entry_price=entry_price,
            supertrend=supertrend,
            side='Buy',
            atr=atr,
            swing_low=swing_low
        )

        # Get leverage for this symbol
        leverage = self.config.get_leverage_for_symbol(self.config.symbol)

        # Calculate position size
        position_size_usdt = self.risk_manager.calculate_position_size(
            balance=balance,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage
        )

        # Convert to quantity
        qty = position_size_usdt / entry_price

        # Validate order
        is_valid, reason = self.risk_manager.validate_order(balance, position_size_usdt, entry_price)
        if not is_valid:
            logger.error(f"Order validation failed: {reason}")
            return

        # NO TAKE PROFIT - exit by market signal only
        take_profit = None

        logger.info(
            f"Opening LONG: qty={qty:.4f}, entry={entry_price:.2f}, leverage={leverage}x, "
            f"SL={stop_loss:.2f} (swing low: {swing_low:.2f if swing_low else 'N/A'}), TP=Market Exit"
        )

        # Place order
        self.client.place_order(
            symbol=self.config.symbol,
            side='Buy',
            qty=qty,
            order_type='Market',
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Record trade in history
        self.current_trade_id = str(uuid.uuid4())
        self.trade_history.add_trade(
            trade_id=self.current_trade_id,
            symbol=self.config.symbol,
            direction='long',
            entry_price=entry_price,
            size=qty,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Send Telegram notification
        self.telegram.notify_position_opened(
            symbol=self.config.symbol,
            direction='LONG',
            entry_price=entry_price,
            quantity=qty,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        self.position_entry_price = entry_price
        logger.info("LONG position opened successfully")

        # Add signal to recent signals
        self._add_signal('buy', self.config.symbol, entry_price)

        # Add to recent trades
        self._add_recent_trade('long', self.config.symbol, entry_price, qty)

    def _open_short(self, signal_data: dict, balance: float):
        """Open short position.

        Args:
            signal_data: Signal data
            balance: Account balance
        """
        entry_price = signal_data['close']
        supertrend = signal_data['supertrend']
        atr = signal_data['atr']
        swing_high = signal_data.get('swing_high')

        # Calculate stop loss using swing high
        stop_loss = self.strategy.calculate_stop_loss(
            entry_price=entry_price,
            supertrend=supertrend,
            side='Sell',
            atr=atr,
            swing_high=swing_high
        )

        # Get leverage for this symbol
        leverage = self.config.get_leverage_for_symbol(self.config.symbol)

        # Calculate position size
        position_size_usdt = self.risk_manager.calculate_position_size(
            balance=balance,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage
        )

        # Convert to quantity
        qty = position_size_usdt / entry_price

        # Validate order
        is_valid, reason = self.risk_manager.validate_order(balance, position_size_usdt, entry_price)
        if not is_valid:
            logger.error(f"Order validation failed: {reason}")
            return

        # NO TAKE PROFIT - exit by market signal only
        take_profit = None

        logger.info(
            f"Opening SHORT: qty={qty:.4f}, entry={entry_price:.2f}, leverage={leverage}x, "
            f"SL={stop_loss:.2f} (swing high: {swing_high:.2f if swing_high else 'N/A'}), TP=Market Exit"
        )

        # Place order
        self.client.place_order(
            symbol=self.config.symbol,
            side='Sell',
            qty=qty,
            order_type='Market',
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Record trade in history
        self.current_trade_id = str(uuid.uuid4())
        self.trade_history.add_trade(
            trade_id=self.current_trade_id,
            symbol=self.config.symbol,
            direction='short',
            entry_price=entry_price,
            size=qty,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Get leverage for this symbol
        leverage = self.config.get_leverage_for_symbol(self.config.symbol)

        # Send Telegram notification
        self.telegram.notify_position_opened(
            symbol=self.config.symbol,
            direction='SHORT',
            entry_price=entry_price,
            quantity=qty,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        self.position_entry_price = entry_price
        logger.info("SHORT position opened successfully")

        # Add signal to recent signals
        self._add_signal('sell', self.config.symbol, entry_price)

        # Add to recent trades
        self._add_recent_trade('short', self.config.symbol, entry_price, qty)

    def _close_position(self, position: dict):
        """Close current position.

        Args:
            position: Position to close
        """
        if not position:
            logger.warning("No position to close")
            return

        logger.info(f"Closing {position['side']} position: size={position['size']}")

        # Close position
        self.client.close_position(
            symbol=self.config.symbol,
            side=position['side'],
            qty=position['size']
        )

        # Record PnL
        pnl = position['unrealized_pnl']
        self.risk_manager.record_trade(pnl, symbol=self.config.symbol)

        # Get exit price and calculate PnL percent
        exit_price = self.current_price if self.current_price > 0 else position.get('entry_price', 0)
        entry_price = position.get('entry_price', 0)
        pnl_percent = (pnl / (entry_price * position['size']) * 100) if position['size'] > 0 else 0

        # Close trade in history
        if self.current_trade_id:
            self.trade_history.close_trade(
                trade_id=self.current_trade_id,
                exit_price=exit_price,
                exit_reason='signal'
            )
            self.current_trade_id = None

        # Send Telegram notification
        direction = 'LONG' if position['side'] == 'Buy' else 'SHORT'
        self.telegram.notify_position_closed(
            symbol=self.config.symbol,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=position['size'],
            pnl=pnl,
            pnl_percent=pnl_percent,
            reason='signal'
        )

        # Update PnL for the most recent trade
        if self.recent_trades and len(self.recent_trades) > 0:
            self.recent_trades[0]['pnl'] = pnl

        # Reset strategy memory
        self.strategy.reset_signal_memory()
        self.position_entry_price = None

        logger.info(f"Position closed. PnL: {pnl:.2f} USDT")

    def _get_interval_string(self) -> str:
        """Get OKX interval string from config.

        Returns:
            Interval string
        """
        tf = self.config.timeframe
        if tf < 60:
            return f"{tf}m"
        elif tf == 60:
            return "1H"
        elif tf == 120:
            return "2H"
        elif tf == 240:
            return "4H"
        elif tf == 360:
            return "6H"
        elif tf == 720:
            return "12H"
        elif tf == 1440:
            return "1D"
        else:
            hours = tf // 60
            return f"{hours}H"

    def _update_dashboard_state(self, balance: float, position: Optional[dict]):
        """Update dashboard state with current data.

        Args:
            balance: Current balance
            position: Current position
        """
        try:
            # Import here to avoid circular dependency
            from . import dashboard_api

            # Calculate equity
            equity = balance
            if position:
                equity += position.get('unrealized_pnl', 0)

            # Prepare open positions for dashboard
            open_positions = []
            if position:
                direction = 'long' if position['side'] == 'Buy' else 'short'
                pnl = position.get('unrealized_pnl', 0)
                pnl_percent = (pnl / (position['entry_price'] * position['size']) * 100) if position['size'] > 0 else 0

                open_positions.append({
                    'direction': direction,
                    'size': position['size'],
                    'entry_price': position['entry_price'],
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                })

            # Get statistics
            statistics = self.trade_history.get_statistics()

            # Get daily PnL
            daily_pnl = self.trade_history.get_daily_pnl()

            # Get weekly stats
            weekly_stats = self.trade_history.get_weekly_stats(starting_balance=balance)

            # Update dashboard
            dashboard_api.update_bot_state(
                balance=balance,
                equity=equity,
                open_positions=open_positions,
                statistics=statistics,
                daily_pnl=daily_pnl,
                weekly_stats=weekly_stats,
                current_price=self.current_price,
                symbol=self.config.symbol,
                is_running=self.running,
                trading_pairs=[self.config.symbol] if self.running else [],
                signals=self.recent_signals,
                recent_trades=self.recent_trades
            )

        except Exception as e:
            logger.debug(f"Error updating dashboard: {e}")

    def _add_signal(self, signal_type: str, symbol: str, price: float):
        """Add signal to recent signals list.

        Args:
            signal_type: 'buy' or 'sell'
            symbol: Trading symbol
            price: Signal price
        """
        signal = {
            'type': signal_type,
            'symbol': symbol,
            'price': price,
            'time': datetime.now().strftime('%H:%M:%S')
        }
        self.recent_signals.insert(0, signal)
        if len(self.recent_signals) > self.max_recent_items:
            self.recent_signals = self.recent_signals[:self.max_recent_items]

    def _add_recent_trade(self, direction: str, symbol: str, entry_price: float, size: float):
        """Add trade to recent trades list.

        Args:
            direction: 'long' or 'short'
            symbol: Trading symbol
            entry_price: Entry price
            size: Position size
        """
        trade = {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'size': size,
            'pnl': 0.0,  # Will be updated when position closes
            'time': datetime.now().strftime('%H:%M:%S')
        }
        self.recent_trades.insert(0, trade)
        if len(self.recent_trades) > self.max_recent_items:
            self.recent_trades = self.recent_trades[:self.max_recent_items]

    def _print_status(self, signal_data: dict, position: Optional[dict], balance: float):
        """Print current status.

        Args:
            signal_data: Signal data
            position: Current position
            balance: Account balance
        """
        logger.info("-" * 60)
        logger.info(f"Price: {signal_data['close']:.2f} | ST: {signal_data['supertrend']:.2f}")
        logger.info(f"Direction: {'BULLISH' if signal_data['direction'] == 1 else 'BEARISH'}")
        logger.info(f"ATR: {signal_data['atr']:.2f}")

        if position:
            logger.info(
                f"Position: {position['side']} {position['size']:.4f} @ {position['entry_price']:.2f} "
                f"| PnL: {position['unrealized_pnl']:.2f}"
            )
        else:
            logger.info("Position: None")

        stats = self.risk_manager.get_daily_stats()
        logger.info(
            f"Daily: PnL={stats['daily_pnl']:.2f} ({stats['daily_loss_pct']:.2f}%) | "
            f"Trades={stats['daily_trades']}"
        )
        logger.info("-" * 60)

    def _print_summary(self):
        """Print trading summary."""
        stats = self.risk_manager.get_daily_stats()
        logger.info("=" * 60)
        logger.info("TRADING SUMMARY")
        logger.info(f"Daily PnL: {stats['daily_pnl']:.2f} USDT ({stats['daily_loss_pct']:.2f}%)")
        logger.info(f"Total Trades: {stats['daily_trades']}")
        logger.info(f"Consecutive Losses: {stats['consecutive_losses']}")
        logger.info("=" * 60)
