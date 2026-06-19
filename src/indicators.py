"""Technical indicators calculation."""
import logging
from typing import List, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR).

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period

    Returns:
        ATR series
    """
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()

    return atr


def calculate_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    atr_period: int = 10,
    multiplier: float = 3.0
) -> Tuple[pd.Series, pd.Series]:
    """Calculate Supertrend indicator.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        atr_period: Period for ATR calculation
        multiplier: ATR multiplier

    Returns:
        Tuple of (supertrend, direction)
        - supertrend: Supertrend line values
        - direction: 1 for bullish, -1 for bearish
    """
    atr = calculate_atr(high, low, close, atr_period)
    hl_avg = (high + low) / 2

    # Calculate basic upper and lower bands
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)

    # Initialize supertrend and direction
    supertrend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=float)

    # Set initial values
    supertrend.iloc[0] = lower_band.iloc[0]
    direction.iloc[0] = 1

    for i in range(1, len(close)):
        # Determine current direction based on previous close vs previous supertrend
        if close.iloc[i - 1] <= supertrend.iloc[i - 1]:
            current_direction = -1  # Downtrend
        else:
            current_direction = 1   # Uptrend

        # Update bands based on direction
        if current_direction == 1:
            # In uptrend, use lower band
            if lower_band.iloc[i] > supertrend.iloc[i - 1]:
                final_band = lower_band.iloc[i]
            else:
                final_band = max(lower_band.iloc[i], supertrend.iloc[i - 1])
        else:
            # In downtrend, use upper band
            if upper_band.iloc[i] < supertrend.iloc[i - 1]:
                final_band = upper_band.iloc[i]
            else:
                final_band = min(upper_band.iloc[i], supertrend.iloc[i - 1])

        # Check if trend changes
        if current_direction == 1 and close.iloc[i] <= final_band:
            # Switch to downtrend
            direction.iloc[i] = -1
            supertrend.iloc[i] = upper_band.iloc[i]
        elif current_direction == -1 and close.iloc[i] >= final_band:
            # Switch to uptrend
            direction.iloc[i] = 1
            supertrend.iloc[i] = lower_band.iloc[i]
        else:
            # Continue current trend
            direction.iloc[i] = current_direction
            supertrend.iloc[i] = final_band

    logger.debug(f"Supertrend calculated: last direction={direction.iloc[-1]}")
    return supertrend, direction


def calculate_ema(close: pd.Series, period: int = 200) -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        close: Close prices
        period: EMA period

    Returns:
        EMA series
    """
    return close.ewm(span=period, adjust=False).mean()


def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate Simple Moving Average of volume.

    Args:
        volume: Volume data
        period: SMA period

    Returns:
        Volume SMA series
    """
    return volume.rolling(window=period).mean()


class IndicatorCalculator:
    """Helper class for calculating indicators from kline data."""

    @staticmethod
    def prepare_dataframe(klines: List[dict]) -> pd.DataFrame:
        """Convert klines list to pandas DataFrame.

        Args:
            klines: List of kline dictionaries

        Returns:
            DataFrame with OHLCV data
        """
        df = pd.DataFrame(klines)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    @staticmethod
    def calculate_all_indicators(
        klines: List[dict],
        atr_period: int = 10,
        supertrend_multiplier: float = 3.0,
        ema_period: int = 200,
        volume_period: int = 20
    ) -> pd.DataFrame:
        """Calculate all indicators for given klines.

        Args:
            klines: List of kline dictionaries
            atr_period: ATR period
            supertrend_multiplier: Supertrend multiplier
            ema_period: EMA period
            volume_period: Volume SMA period

        Returns:
            DataFrame with all indicators
        """
        df = IndicatorCalculator.prepare_dataframe(klines)

        # Calculate Supertrend
        df['supertrend'], df['st_direction'] = calculate_supertrend(
            df['high'],
            df['low'],
            df['close'],
            atr_period,
            supertrend_multiplier
        )

        # Calculate ATR
        df['atr'] = calculate_atr(df['high'], df['low'], df['close'], atr_period)

        # Calculate EMA
        df['ema'] = calculate_ema(df['close'], ema_period)

        # Calculate Volume SMA
        df['volume_sma'] = calculate_volume_sma(df['volume'], volume_period)

        logger.debug(f"Calculated indicators for {len(df)} candles")
        return df

    @staticmethod
    def get_latest_signal(df: pd.DataFrame) -> dict:
        """Extract latest signal from indicator DataFrame.

        Args:
            df: DataFrame with indicators

        Returns:
            Dictionary with latest signal data
        """
        latest = df.iloc[-1]
        previous = df.iloc[-2] if len(df) > 1 else None

        # Find swing low and swing high
        swing_low = IndicatorCalculator.find_swing_low(df, lookback=20)
        swing_high = IndicatorCalculator.find_swing_high(df, lookback=20)

        signal = {
            'close': latest['close'],
            'supertrend': latest['supertrend'],
            'direction': latest['st_direction'],
            'atr': latest['atr'],
            'ema': latest.get('ema', None),
            'volume': latest['volume'],
            'volume_sma': latest.get('volume_sma', None),
            'prev_direction': previous['st_direction'] if previous is not None else None,
            'swing_low': swing_low,
            'swing_high': swing_high,
        }

        return signal

    @staticmethod
    def find_swing_low(df: pd.DataFrame, lookback: int = 20) -> float:
        """Find recent swing low (previous local minimum).

        Args:
            df: DataFrame with OHLC data
            lookback: Number of bars to look back

        Returns:
            Swing low price
        """
        if len(df) < lookback:
            lookback = len(df)

        # Get recent lows
        recent_lows = df['low'].iloc[-lookback:]

        # Find the minimum low
        swing_low = recent_lows.min()

        return swing_low

    @staticmethod
    def find_swing_high(df: pd.DataFrame, lookback: int = 20) -> float:
        """Find recent swing high (previous local maximum).

        Args:
            df: DataFrame with OHLC data
            lookback: Number of bars to look back

        Returns:
            Swing high price
        """
        if len(df) < lookback:
            lookback = len(df)

        # Get recent highs
        recent_highs = df['high'].iloc[-lookback:]

        # Find the maximum high
        swing_high = recent_highs.max()

        return swing_high
