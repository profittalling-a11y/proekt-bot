"""Trading strategy implementation."""
import logging
from typing import Optional, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class Signal(str, Enum):
    """Trading signals."""
    LONG = "long"
    SHORT = "short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    HOLD = "hold"


class SupertrendStrategy:
    """Supertrend-based trading strategy."""

    def __init__(
        self,
        use_ema_filter: bool = False,
        ema_period: int = 200,
        use_volume_filter: bool = False,
        min_volume_multiplier: float = 1.5
    ):
        """Initialize strategy.

        Args:
            use_ema_filter: Enable EMA filter
            ema_period: EMA period for filter
            use_volume_filter: Enable volume filter
            min_volume_multiplier: Minimum volume multiplier vs average
        """
        self.use_ema_filter = use_ema_filter
        self.ema_period = ema_period
        self.use_volume_filter = use_volume_filter
        self.min_volume_multiplier = min_volume_multiplier

        self.last_signal_direction = None
        self.last_signal_price = None

        # Track trend for dashboard
        self.last_trend = None  # 'bullish' or 'bearish'
        self.previous_trend = None

        logger.info(
            f"Strategy initialized: EMA filter={use_ema_filter}, "
            f"Volume filter={use_volume_filter}"
        )

    def generate_signal(
        self,
        signal_data: Dict,
        current_position: Optional[Dict] = None
    ) -> Signal:
        """Generate trading signal based on Supertrend.

        Args:
            signal_data: Dictionary with indicator values
            current_position: Current position info (if any)

        Returns:
            Trading signal
        """
        close = signal_data['close']
        direction = signal_data['direction']
        prev_direction = signal_data['prev_direction']
        supertrend = signal_data['supertrend']

        # Update trend tracking
        current_trend = 'bullish' if direction == 1 else 'bearish' if direction == -1 else None
        if current_trend != self.last_trend:
            self.previous_trend = self.last_trend
            self.last_trend = current_trend
            if self.previous_trend:
                logger.info(f"Trend changed: {self.previous_trend} -> {self.last_trend}")

        # Check if direction changed (signal confirmation)
        direction_changed = prev_direction is not None and direction != prev_direction

        if not direction_changed:
            # No direction change, check if we need to close position
            if current_position:
                return self._check_exit_signal(signal_data, current_position)
            return Signal.HOLD

        # Direction changed - potential entry signal
        logger.info(
            f"Supertrend direction changed: {prev_direction} -> {direction} "
            f"(price: {close}, ST: {supertrend:.2f})"
        )

        # Apply filters
        if not self._pass_filters(signal_data):
            logger.info("Signal filtered out")
            return Signal.HOLD

        # Prevent duplicate signals
        if self._is_duplicate_signal(direction, close):
            logger.info("Duplicate signal detected, skipping")
            return Signal.HOLD

        # Generate entry signal
        if direction == 1:  # Bullish
            if current_position:
                if current_position['side'] == 'Sell':
                    logger.info("Closing SHORT position on bullish signal")
                    return Signal.CLOSE_SHORT
                else:
                    return Signal.HOLD
            else:
                logger.info("LONG signal generated")
                self.last_signal_direction = 1
                self.last_signal_price = close
                return Signal.LONG

        elif direction == -1:  # Bearish
            if current_position:
                if current_position['side'] == 'Buy':
                    logger.info("Closing LONG position on bearish signal")
                    return Signal.CLOSE_LONG
                else:
                    return Signal.HOLD
            else:
                logger.info("SHORT signal generated")
                self.last_signal_direction = -1
                self.last_signal_price = close
                return Signal.SHORT

        return Signal.HOLD

    def _check_exit_signal(
        self,
        signal_data: Dict,
        position: Dict
    ) -> Signal:
        """Check if position should be closed based on Supertrend.

        Args:
            signal_data: Signal data
            position: Current position

        Returns:
            Exit signal or HOLD
        """
        close = signal_data['close']
        supertrend = signal_data['supertrend']
        direction = signal_data['direction']

        # Close long if price crosses below Supertrend
        if position['side'] == 'Buy' and direction == -1:
            logger.info(f"Exit LONG: price {close} crossed below ST {supertrend:.2f}")
            return Signal.CLOSE_LONG

        # Close short if price crosses above Supertrend
        if position['side'] == 'Sell' and direction == 1:
            logger.info(f"Exit SHORT: price {close} crossed above ST {supertrend:.2f}")
            return Signal.CLOSE_SHORT

        return Signal.HOLD

    def _pass_filters(self, signal_data: Dict) -> bool:
        """Check if signal passes all filters.

        Args:
            signal_data: Signal data

        Returns:
            True if all filters pass
        """
        close = signal_data['close']
        direction = signal_data['direction']

        # EMA filter
        if self.use_ema_filter:
            ema = signal_data.get('ema')
            if ema is None:
                logger.warning("EMA filter enabled but EMA not calculated")
                return False

            # Only long above EMA, only short below EMA
            if direction == 1 and close < ema:
                logger.info(f"EMA filter: LONG rejected (price {close} < EMA {ema:.2f})")
                return False
            if direction == -1 and close > ema:
                logger.info(f"EMA filter: SHORT rejected (price {close} > EMA {ema:.2f})")
                return False

        # Volume filter
        if self.use_volume_filter:
            volume = signal_data.get('volume')
            volume_sma = signal_data.get('volume_sma')

            if volume is None or volume_sma is None:
                logger.warning("Volume filter enabled but volume data not available")
                return False

            if volume < volume_sma * self.min_volume_multiplier:
                logger.info(
                    f"Volume filter: rejected (volume {volume:.0f} < "
                    f"{self.min_volume_multiplier}x SMA {volume_sma:.0f})"
                )
                return False

        return True

    def _is_duplicate_signal(self, direction: float, price: float) -> bool:
        """Check if this is a duplicate signal.

        Args:
            direction: Signal direction
            price: Current price

        Returns:
            True if duplicate
        """
        if self.last_signal_direction == direction:
            # Same direction as last signal
            if self.last_signal_price is not None:
                price_change_pct = abs(price - self.last_signal_price) / self.last_signal_price * 100
                # Consider duplicate if price hasn't moved significantly (< 0.5%)
                if price_change_pct < 0.5:
                    return True

        return False

    def reset_signal_memory(self):
        """Reset signal memory (call after position is closed)."""
        self.last_signal_direction = None
        self.last_signal_price = None
        logger.debug("Signal memory reset")

    def calculate_stop_loss(
        self,
        entry_price: float,
        supertrend: float,
        side: str,
        atr: float,
        swing_low: Optional[float] = None,
        swing_high: Optional[float] = None,
        buffer_multiplier: float = 0.1
    ) -> float:
        """Calculate stop loss based on swing levels (previous low/high).

        Args:
            entry_price: Entry price
            supertrend: Current Supertrend value
            side: Position side (Buy/Sell)
            atr: Current ATR value
            swing_low: Previous swing low (for LONG)
            swing_high: Previous swing high (for SHORT)
            buffer_multiplier: Buffer multiplier for ATR (default 0.1 = 10% ATR)

        Returns:
            Stop loss price
        """
        buffer = atr * buffer_multiplier

        if side == 'Buy':
            # For LONG: stop below previous swing low or Supertrend (whichever is lower)
            if swing_low is not None:
                stop_loss = swing_low - buffer
                logger.info(f"LONG SL: {stop_loss:.2f} (swing low: {swing_low:.2f} - buffer: {buffer:.2f})")
            else:
                # Fallback to Supertrend if no swing low
                stop_loss = supertrend - buffer
                logger.info(f"LONG SL: {stop_loss:.2f} (Supertrend: {supertrend:.2f} - buffer: {buffer:.2f})")
        else:
            # For SHORT: stop above previous swing high or Supertrend (whichever is higher)
            if swing_high is not None:
                stop_loss = swing_high + buffer
                logger.info(f"SHORT SL: {stop_loss:.2f} (swing high: {swing_high:.2f} + buffer: {buffer:.2f})")
            else:
                # Fallback to Supertrend if no swing high
                stop_loss = supertrend + buffer
                logger.info(f"SHORT SL: {stop_loss:.2f} (Supertrend: {supertrend:.2f} + buffer: {buffer:.2f})")

        return stop_loss

    def calculate_take_profit(
        self,
        entry_price: float,
        side: str,
        risk_reward_ratio: float = 2.0,
        stop_loss: Optional[float] = None
    ) -> Optional[float]:
        """Calculate take profit based on risk-reward ratio.

        Args:
            entry_price: Entry price
            side: Position side
            risk_reward_ratio: Risk-reward ratio
            stop_loss: Stop loss price

        Returns:
            Take profit price or None
        """
        if stop_loss is None:
            return None

        risk = abs(entry_price - stop_loss)
        reward = risk * risk_reward_ratio

        if side == 'Buy':
            take_profit = entry_price + reward
        else:
            take_profit = entry_price - reward

        logger.debug(
            f"Calculated TP: {take_profit:.2f} "
            f"(entry: {entry_price:.2f}, SL: {stop_loss:.2f}, R:R={risk_reward_ratio})"
        )
        return take_profit
