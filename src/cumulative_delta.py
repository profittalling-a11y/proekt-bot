"""Cumulative Delta analysis for trend change detection.

Cumulative Delta = Σ(Buy Volume - Sell Volume)

When cumulative delta diverges from price:
- Price makes new high, but delta makes lower high → bearish divergence (trend reversal down)
- Price makes new low, but delta makes higher low → bullish divergence (trend reversal up)
"""
import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DeltaSignal:
    """Signal from cumulative delta analysis."""
    symbol: str
    direction: str  # 'buy', 'sell', 'neutral'
    strength: float  # 0.0 to 1.0
    divergence_type: str  # 'bullish_divergence', 'bearish_divergence', 'none'
    price_trend: str  # 'up', 'down', 'sideways'
    delta_trend: str  # 'up', 'down', 'sideways'
    reason: str


class CumulativeDeltaAnalyzer:
    """Analyzes cumulative delta for trend change detection."""

    def __init__(self, lookback_period: int = 50, divergence_window: int = 20):
        """Initialize analyzer.

        Args:
            lookback_period: Number of candles to analyze
            divergence_window: Window for detecting divergences
        """
        self.lookback_period = lookback_period
        self.divergence_window = divergence_window
        self.delta_history: Dict[str, List[float]] = {}

    def calculate_cumulative_delta(self, klines: List[Dict]) -> List[float]:
        """Calculate cumulative delta from kline data.

        Uses volume and close price to estimate buy/sell pressure:
        - If close > open: buy volume = volume * (close - low) / (high - low)
        - If close < open: sell volume = volume * (high - close) / (high - low)
        - Otherwise: split 50/50

        Args:
            klines: List of OHLCV candles

        Returns:
            List of cumulative delta values
        """
        cumulative_delta = []
        running_delta = 0.0

        for candle in klines:
            open_p = candle['open']
            high = candle['high']
            low = candle['low']
            close = candle['close']
            volume = candle['volume']

            if high == low:
                buy_volume = volume / 2
                sell_volume = volume / 2
            elif close > open_p:
                # Bullish candle - more buying pressure
                buy_volume = volume * (close - low) / (high - low)
                sell_volume = volume - buy_volume
            elif close < open_p:
                # Bearish candle - more selling pressure
                sell_volume = volume * (high - close) / (high - low)
                buy_volume = volume - sell_volume
            else:
                buy_volume = volume / 2
                sell_volume = volume / 2

            delta = buy_volume - sell_volume
            running_delta += delta
            cumulative_delta.append(running_delta)

        return cumulative_delta

    def detect_divergence(
        self,
        prices: List[float],
        deltas: List[float]
    ) -> Tuple[str, str]:
        """Detect divergence between price and cumulative delta.

        Args:
            prices: List of close prices
            deltas: List of cumulative delta values

        Returns:
            Tuple of (divergence_type, signal_direction)
        """
        if len(prices) < self.divergence_window or len(deltas) < self.divergence_window:
            return 'none', 'neutral'

        recent_prices = prices[-self.divergence_window:]
        recent_deltas = deltas[-self.divergence_window:]

        # Find local highs and lows in price
        price_high = max(recent_prices)
        price_low = min(recent_prices)
        price_high_idx = recent_prices.index(price_high)
        price_low_idx = recent_prices.index(price_low)

        # Find corresponding delta values
        delta_at_price_high = recent_deltas[price_high_idx] if price_high_idx < len(recent_deltas) else 0
        delta_at_price_low = recent_deltas[price_low_idx] if price_low_idx < len(recent_deltas) else 0

        # Check for bearish divergence: price high but delta not confirming
        if price_high_idx > len(recent_prices) // 2:
            # Recent high
            prev_price_high = max(recent_prices[:len(recent_prices)//2])
            prev_delta_at_high = 0
            for i in range(len(recent_prices)//2):
                if recent_prices[i] == prev_price_high:
                    prev_delta_at_high = recent_deltas[i]
                    break

            if price_high > prev_price_high and delta_at_price_high < prev_delta_at_high:
                return 'bearish_divergence', 'sell'

        # Check for bullish divergence: price low but delta not confirming
        if price_low_idx > len(recent_prices) // 2:
            # Recent low
            prev_price_low = min(recent_prices[:len(recent_prices)//2])
            prev_delta_at_low = 0
            for i in range(len(recent_prices)//2):
                if recent_prices[i] == prev_price_low:
                    prev_delta_at_low = recent_deltas[i]
                    break

            if price_low < prev_price_low and delta_at_price_low > prev_delta_at_low:
                return 'bullish_divergence', 'buy'

        return 'none', 'neutral'

    def analyze(
        self,
        symbol: str,
        klines: List[Dict]
    ) -> DeltaSignal:
        """Perform full cumulative delta analysis.

        Args:
            symbol: Trading symbol
            klines: List of OHLCV candles

        Returns:
            DeltaSignal with analysis results
        """
        if len(klines) < self.lookback_period:
            return DeltaSignal(
                symbol=symbol,
                direction='neutral',
                strength=0.0,
                divergence_type='none',
                price_trend='sideways',
                delta_trend='sideways',
                reason='Insufficient data'
            )

        # Use last N candles
        recent_klines = klines[-self.lookback_period:]
        prices = [k['close'] for k in recent_klines]

        # Calculate cumulative delta
        cumulative_delta = self.calculate_cumulative_delta(recent_klines)

        # Detect divergence
        divergence_type, signal_direction = self.detect_divergence(prices, cumulative_delta)

        # Determine price trend
        if prices[-1] > prices[0] * 1.02:
            price_trend = 'up'
        elif prices[-1] < prices[0] * 0.98:
            price_trend = 'down'
        else:
            price_trend = 'sideways'

        # Determine delta trend
        if cumulative_delta[-1] > cumulative_delta[0]:
            delta_trend = 'up'
        elif cumulative_delta[-1] < cumulative_delta[0]:
            delta_trend = 'down'
        else:
            delta_trend = 'sideways'

        # Calculate signal strength
        strength = 0.0
        reason = 'No divergence detected'

        if divergence_type == 'bearish_divergence':
            strength = 0.8
            reason = 'Bearish divergence: price higher but delta weakening'
            signal_direction = 'sell'
        elif divergence_type == 'bullish_divergence':
            strength = 0.8
            reason = 'Bullish divergence: price lower but delta strengthening'
            signal_direction = 'buy'
        elif price_trend != delta_trend and price_trend != 'sideways':
            # Trend mismatch - potential reversal
            strength = 0.5
            if price_trend == 'up' and delta_trend == 'down':
                signal_direction = 'sell'
                reason = 'Price rising but delta falling - potential reversal'
            elif price_trend == 'down' and delta_trend == 'up':
                signal_direction = 'buy'
                reason = 'Price falling but delta rising - potential reversal'

        return DeltaSignal(
            symbol=symbol,
            direction=signal_direction,
            strength=strength,
            divergence_type=divergence_type,
            price_trend=price_trend,
            delta_trend=delta_trend,
            reason=reason
        )
