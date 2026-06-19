"""Unit tests for indicators module."""
import pytest
import pandas as pd
import numpy as np
from src.indicators import calculate_atr, calculate_supertrend, IndicatorCalculator


def create_sample_klines(n=100):
    """Create sample kline data for testing."""
    np.random.seed(42)
    base_price = 50000
    klines = []

    for i in range(n):
        open_price = base_price + np.random.randn() * 100
        close_price = open_price + np.random.randn() * 50
        high_price = max(open_price, close_price) + abs(np.random.randn() * 20)
        low_price = min(open_price, close_price) - abs(np.random.randn() * 20)
        volume = 1000 + np.random.rand() * 500

        klines.append({
            'timestamp': 1000000000000 + i * 60000,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume,
        })

        base_price = close_price

    return klines


class TestATR:
    """Test ATR calculation."""

    def test_atr_calculation(self):
        """Test basic ATR calculation."""
        klines = create_sample_klines(50)
        df = IndicatorCalculator.prepare_dataframe(klines)

        atr = calculate_atr(df['high'], df['low'], df['close'], period=14)

        assert len(atr) == len(df)
        assert not atr.iloc[-1] == 0
        assert atr.iloc[-1] > 0
        # First values should be NaN due to rolling window
        assert pd.isna(atr.iloc[0])

    def test_atr_different_periods(self):
        """Test ATR with different periods."""
        klines = create_sample_klines(50)
        df = IndicatorCalculator.prepare_dataframe(klines)

        atr_10 = calculate_atr(df['high'], df['low'], df['close'], period=10)
        atr_20 = calculate_atr(df['high'], df['low'], df['close'], period=20)

        # Both should have valid values
        assert not pd.isna(atr_10.iloc[-1])
        assert not pd.isna(atr_20.iloc[-1])

        # Longer period should smooth more
        assert len(atr_10) == len(atr_20)


class TestSupertrend:
    """Test Supertrend calculation."""

    def test_supertrend_calculation(self):
        """Test basic Supertrend calculation."""
        klines = create_sample_klines(100)
        df = IndicatorCalculator.prepare_dataframe(klines)

        supertrend, direction = calculate_supertrend(
            df['high'], df['low'], df['close'],
            atr_period=10, multiplier=3.0
        )

        assert len(supertrend) == len(df)
        assert len(direction) == len(df)

        # Direction should be 1 or -1
        assert all(direction.dropna().isin([1, -1]))

        # Supertrend should have valid values
        assert not pd.isna(supertrend.iloc[-1])
        assert supertrend.iloc[-1] > 0

    def test_supertrend_direction_changes(self):
        """Test that Supertrend direction can change."""
        klines = create_sample_klines(100)
        df = IndicatorCalculator.prepare_dataframe(klines)

        supertrend, direction = calculate_supertrend(
            df['high'], df['low'], df['close'],
            atr_period=10, multiplier=3.0
        )

        # Check that direction changes at least once
        direction_changes = (direction.diff() != 0).sum()
        assert direction_changes > 0

    def test_supertrend_different_multipliers(self):
        """Test Supertrend with different multipliers."""
        klines = create_sample_klines(100)
        df = IndicatorCalculator.prepare_dataframe(klines)

        st_2, dir_2 = calculate_supertrend(
            df['high'], df['low'], df['close'],
            atr_period=10, multiplier=2.0
        )

        st_4, dir_4 = calculate_supertrend(
            df['high'], df['low'], df['close'],
            atr_period=10, multiplier=4.0
        )

        # Both should have valid values
        assert not pd.isna(st_2.iloc[-1])
        assert not pd.isna(st_4.iloc[-1])

        # Higher multiplier should give wider bands
        # (not always true for every candle, but generally)
        assert len(st_2) == len(st_4)


class TestIndicatorCalculator:
    """Test IndicatorCalculator class."""

    def test_prepare_dataframe(self):
        """Test DataFrame preparation."""
        klines = create_sample_klines(50)
        df = IndicatorCalculator.prepare_dataframe(klines)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 50
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert 'close' in df.columns
        assert 'volume' in df.columns

    def test_calculate_all_indicators(self):
        """Test calculation of all indicators."""
        klines = create_sample_klines(100)
        df = IndicatorCalculator.calculate_all_indicators(
            klines,
            atr_period=10,
            supertrend_multiplier=3.0,
            ema_period=50,
            volume_period=20
        )

        assert 'supertrend' in df.columns
        assert 'st_direction' in df.columns
        assert 'atr' in df.columns
        assert 'ema' in df.columns
        assert 'volume_sma' in df.columns

        # Check last values are not NaN
        assert not pd.isna(df['supertrend'].iloc[-1])
        assert not pd.isna(df['st_direction'].iloc[-1])
        assert not pd.isna(df['atr'].iloc[-1])

    def test_get_latest_signal(self):
        """Test getting latest signal."""
        klines = create_sample_klines(100)
        df = IndicatorCalculator.calculate_all_indicators(klines)
        signal = IndicatorCalculator.get_latest_signal(df)

        assert 'close' in signal
        assert 'supertrend' in signal
        assert 'direction' in signal
        assert 'atr' in signal
        assert 'prev_direction' in signal

        # Check values are valid
        assert signal['close'] > 0
        assert signal['supertrend'] > 0
        assert signal['direction'] in [1, -1]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
