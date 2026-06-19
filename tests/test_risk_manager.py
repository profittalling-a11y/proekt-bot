"""Unit tests for risk_manager module."""
import pytest
from src.risk_manager import RiskManager


class TestRiskManagerInit:
    """Test RiskManager initialization."""

    def test_default_init(self):
        rm = RiskManager()
        assert rm.fixed_position_size == 1.0
        assert rm.risk_per_position == 2.0
        assert rm.max_positions == 10
        assert rm.max_daily_loss == 20.0
        assert rm.cooldown_after_loss == 300
        assert rm.min_balance == 100.0

    def test_custom_init(self):
        rm = RiskManager(
            fixed_position_size=5.0,
            risk_per_position=1.0,
            max_positions=5,
            max_daily_loss=10.0,
            cooldown_after_loss=600,
            min_balance=50.0
        )
        assert rm.fixed_position_size == 5.0
        assert rm.max_positions == 5


class TestCanTrade:
    """Test can_trade logic."""

    def test_can_trade_normal(self):
        rm = RiskManager(min_balance=10.0, max_positions=10)
        can, reason = rm.can_trade(balance=100.0, symbol="BTC-USDT-SWAP", current_positions=0)
        assert can is True
        assert reason == "OK"

    def test_below_min_balance(self):
        rm = RiskManager(min_balance=100.0)
        can, reason = rm.can_trade(balance=50.0)
        assert can is False
        assert "below minimum" in reason

    def test_max_positions_reached(self):
        rm = RiskManager(max_positions=2)
        can, reason = rm.can_trade(balance=1000.0, current_positions=2)
        assert can is False
        assert "Maximum positions" in reason

    def test_daily_loss_limit(self):
        rm = RiskManager(max_daily_loss=5.0)
        rm.starting_balance = 1000.0
        rm.daily_pnl = -60.0  # -6% loss
        can, reason = rm.can_trade(balance=940.0)
        assert can is False
        assert "Daily loss limit" in reason

    def test_cooldown_after_loss(self):
        import time
        rm = RiskManager(cooldown_after_loss=300)
        rm.last_loss_time["BTC-USDT-SWAP"] = time.time() - 100  # 100s ago
        can, reason = rm.can_trade(balance=1000.0, symbol="BTC-USDT-SWAP")
        assert can is False
        assert "Cooldown" in reason

    def test_cooldown_expired(self):
        import time
        rm = RiskManager(cooldown_after_loss=300)
        rm.last_loss_time["BTC-USDT-SWAP"] = time.time() - 400  # 400s ago
        can, reason = rm.can_trade(balance=1000.0, symbol="BTC-USDT-SWAP")
        assert can is True


class TestPositionSize:
    """Test position size calculation."""

    def test_basic_position_size(self):
        rm = RiskManager(fixed_position_size=1.0)
        size = rm.calculate_position_size(
            balance=100.0,
            entry_price=50000.0,
            stop_loss=49000.0,
            leverage=50
        )
        # balance_multiplier = 100/100 = 1, margin = 1*1 = 1, notional = 1*50 = 50
        assert size == 50.0

    def test_position_size_scales_with_balance(self):
        rm = RiskManager(fixed_position_size=1.0)
        size_100 = rm.calculate_position_size(balance=100.0, entry_price=50000, stop_loss=49000, leverage=50)
        size_300 = rm.calculate_position_size(balance=300.0, entry_price=50000, stop_loss=49000, leverage=50)
        # 300/100 = 3x multiplier
        assert size_300 == size_100 * 3

    def test_position_size_min_multiplier(self):
        rm = RiskManager(fixed_position_size=2.0)
        size = rm.calculate_position_size(balance=50.0, entry_price=50000, stop_loss=49000, leverage=50)
        # 50/100 = 0.5 -> min 1, margin = 2*1 = 2, notional = 2*50 = 100
        assert size == 100.0


class TestRecordTrade:
    """Test trade recording."""

    def test_record_profit(self):
        rm = RiskManager()
        rm.record_trade(pnl=10.0, symbol="BTC-USDT-SWAP")
        assert rm.daily_pnl == 10.0
        assert rm.daily_trades == 1
        assert rm.consecutive_losses.get("BTC-USDT-SWAP", 0) == 0

    def test_record_loss(self):
        rm = RiskManager()
        rm.record_trade(pnl=-10.0, symbol="BTC-USDT-SWAP")
        assert rm.daily_pnl == -10.0
        assert rm.daily_trades == 1
        assert rm.consecutive_losses["BTC-USDT-SWAP"] == 1

    def test_consecutive_losses(self):
        rm = RiskManager()
        rm.record_trade(pnl=-10.0, symbol="BTC-USDT-SWAP")
        rm.record_trade(pnl=-20.0, symbol="BTC-USDT-SWAP")
        rm.record_trade(pnl=-5.0, symbol="BTC-USDT-SWAP")
        assert rm.consecutive_losses["BTC-USDT-SWAP"] == 3

    def test_profit_resets_consecutive_losses(self):
        rm = RiskManager()
        rm.record_trade(pnl=-10.0, symbol="BTC-USDT-SWAP")
        rm.record_trade(pnl=-20.0, symbol="BTC-USDT-SWAP")
        rm.record_trade(pnl=5.0, symbol="BTC-USDT-SWAP")
        assert rm.consecutive_losses["BTC-USDT-SWAP"] == 0


class TestValidateOrder:
    """Test order validation."""

    def test_valid_order(self):
        rm = RiskManager()
        valid, reason = rm.validate_order(balance=1000.0, position_size_usdt=100.0, entry_price=50000)
        assert valid is True

    def test_insufficient_balance(self):
        rm = RiskManager()
        valid, reason = rm.validate_order(balance=50.0, position_size_usdt=100.0, entry_price=50000)
        assert valid is False
        assert "Insufficient balance" in reason

    def test_position_too_small(self):
        rm = RiskManager()
        valid, reason = rm.validate_order(balance=1000.0, position_size_usdt=0.5, entry_price=50000)
        assert valid is False
        assert "too small" in reason


class TestDailyStats:
    """Test daily statistics."""

    def test_daily_stats_empty(self):
        rm = RiskManager()
        stats = rm.get_daily_stats()
        assert stats['daily_pnl'] == 0.0
        assert stats['daily_trades'] == 0

    def test_daily_stats_with_trades(self):
        rm = RiskManager()
        rm.starting_balance = 1000.0
        rm.record_trade(pnl=50.0)
        rm.record_trade(pnl=-20.0)
        stats = rm.get_daily_stats()
        assert stats['daily_pnl'] == 30.0
        assert stats['daily_trades'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
