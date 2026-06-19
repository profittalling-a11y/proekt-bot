"""Unit tests for strategy module."""
import pytest
from src.strategy import SupertrendStrategy, Signal


class TestSupertrendStrategy:
    """Test Supertrend strategy."""

    def test_strategy_initialization(self):
        """Test strategy initialization."""
        strategy = SupertrendStrategy(
            use_ema_filter=True,
            ema_period=200,
            use_volume_filter=True,
            min_volume_multiplier=1.5
        )

        assert strategy.use_ema_filter is True
        assert strategy.ema_period == 200
        assert strategy.use_volume_filter is True
        assert strategy.min_volume_multiplier == 1.5

    def test_long_signal_generation(self):
        """Test long signal generation."""
        strategy = SupertrendStrategy()

        signal_data = {
            'close': 50000,
            'supertrend': 49500,
            'direction': 1,
            'prev_direction': -1,
            'atr': 100,
            'ema': 49000,
            'volume': 1000,
            'volume_sma': 800,
        }

        signal = strategy.generate_signal(signal_data, current_position=None)
        assert signal == Signal.LONG

    def test_short_signal_generation(self):
        """Test short signal generation."""
        strategy = SupertrendStrategy()

        signal_data = {
            'close': 50000,
            'supertrend': 50500,
            'direction': -1,
            'prev_direction': 1,
            'atr': 100,
            'ema': 51000,
            'volume': 1000,
            'volume_sma': 800,
        }

        signal = strategy.generate_signal(signal_data, current_position=None)
        assert signal == Signal.SHORT

    def test_hold_signal_no_direction_change(self):
        """Test hold signal when direction doesn't change."""
        strategy = SupertrendStrategy()

        signal_data = {
            'close': 50000,
            'supertrend': 49500,
            'direction': 1,
            'prev_direction': 1,  # Same direction
            'atr': 100,
            'ema': 49000,
            'volume': 1000,
            'volume_sma': 800,
        }

        signal = strategy.generate_signal(signal_data, current_position=None)
        assert signal == Signal.HOLD

    def test_ema_filter_rejects_long(self):
        """Test EMA filter rejecting long signal."""
        strategy = SupertrendStrategy(use_ema_filter=True)

        signal_data = {
            'close': 50000,
            'supertrend': 49500,
            'direction': 1,
            'prev_direction': -1,
            'atr': 100,
            'ema': 51000,  # Price below EMA
            'volume': 1000,
            'volume_sma': 800,
        }

        signal = strategy.generate_signal(signal_data, current_position=None)
        assert signal == Signal.HOLD

    def test_ema_filter_rejects_short(self):
        """Test EMA filter rejecting short signal."""
        strategy = SupertrendStrategy(use_ema_filter=True)

        signal_data = {
            'close': 50000,
            'supertrend': 50500,
            'direction': -1,
            'prev_direction': 1,
            'atr': 100,
            'ema': 49000,  # Price above EMA
            'volume': 1000,
            'volume_sma': 800,
        }

        signal = strategy.generate_signal(signal_data, current_position=None)
        assert signal == Signal.HOLD

    def test_volume_filter_rejects_signal(self):
        """Test volume filter rejecting signal."""
        strategy = SupertrendStrategy(use_volume_filter=True, min_volume_multiplier=2.0)

        signal_data = {
            'close': 50000,
            'supertrend': 49500,
            'direction': 1,
            'prev_direction': -1,
            'atr': 100,
            'ema': 49000,
            'volume': 1000,
            'volume_sma': 800,  # Volume only 1.25x average, need 2x
        }

        signal = strategy.generate_signal(signal_data, current_position=None)
        assert signal == Signal.HOLD

    def test_close_long_on_bearish_signal(self):
        """Test closing long position on bearish signal."""
        strategy = SupertrendStrategy()

        signal_data = {
            'close': 50000,
            'supertrend': 50500,
            'direction': -1,
            'prev_direction': 1,
            'atr': 100,
            'ema': 49000,
            'volume': 1000,
            'volume_sma': 800,
        }

        position = {
            'side': 'Buy',
            'size': 0.1,
            'entry_price': 49000,
        }

        signal = strategy.generate_signal(signal_data, current_position=position)
        assert signal == Signal.CLOSE_LONG

    def test_duplicate_signal_prevention(self):
        """Test duplicate signal prevention."""
        strategy = SupertrendStrategy()

        signal_data = {
            'close': 50000,
            'supertrend': 49500,
            'direction': 1,
            'prev_direction': -1,
            'atr': 100,
            'ema': 49000,
            'volume': 1000,
            'volume_sma': 800,
        }

        # First signal should work
        signal1 = strategy.generate_signal(signal_data, current_position=None)
        assert signal1 == Signal.LONG

        # Second signal with same direction and similar price should be rejected
        signal_data['close'] = 50010  # Only 0.02% change
        signal_data['prev_direction'] = 1
        signal2 = strategy.generate_signal(signal_data, current_position=None)
        assert signal2 == Signal.HOLD

    def test_calculate_stop_loss_long(self):
        """Test stop loss calculation for long."""
        strategy = SupertrendStrategy()

        stop_loss = strategy.calculate_stop_loss(
            entry_price=50000,
            supertrend=49500,
            side='Buy',
            atr=100,
            buffer_multiplier=0.5
        )

        # Stop should be below supertrend
        assert stop_loss < 49500
        assert stop_loss == 49500 - (100 * 0.5)

    def test_calculate_stop_loss_short(self):
        """Test stop loss calculation for short."""
        strategy = SupertrendStrategy()

        stop_loss = strategy.calculate_stop_loss(
            entry_price=50000,
            supertrend=50500,
            side='Sell',
            atr=100,
            buffer_multiplier=0.5
        )

        # Stop should be above supertrend
        assert stop_loss > 50500
        assert stop_loss == 50500 + (100 * 0.5)

    def test_calculate_take_profit(self):
        """Test take profit calculation."""
        strategy = SupertrendStrategy()

        # Long position
        tp_long = strategy.calculate_take_profit(
            entry_price=50000,
            side='Buy',
            risk_reward_ratio=2.0,
            stop_loss=49500
        )

        # TP should be 2x the risk distance above entry
        risk = 50000 - 49500
        expected_tp = 50000 + (risk * 2)
        assert tp_long == expected_tp

        # Short position
        tp_short = strategy.calculate_take_profit(
            entry_price=50000,
            side='Sell',
            risk_reward_ratio=2.0,
            stop_loss=50500
        )

        # TP should be 2x the risk distance below entry
        risk = 50500 - 50000
        expected_tp = 50000 - (risk * 2)
        assert tp_short == expected_tp


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
