"""Unit tests for config module."""
import pytest
from src.config import Config, Exchange, TradingMode


class TestSymbolNormalization:
    """Test symbol normalization across exchanges."""

    def test_okx_btcusdt(self):
        config = Config(exchange=Exchange.OKX)
        assert config.normalize_symbol("BTCUSDT") == "BTC-USDT-SWAP"

    def test_okx_btc_usdt_swap(self):
        config = Config(exchange=Exchange.OKX)
        assert config.normalize_symbol("BTC-USDT-SWAP") == "BTC-USDT-SWAP"

    def test_okx_btc_usdt(self):
        config = Config(exchange=Exchange.OKX)
        assert config.normalize_symbol("BTC-USDT") == "BTC-USDT-SWAP"

    def test_bybit_btcusdt(self):
        config = Config(exchange=Exchange.BYBIT)
        assert config.normalize_symbol("BTCUSDT") == "BTCUSDT"

    def test_bybit_btc_usdt_swap(self):
        config = Config(exchange=Exchange.BYBIT)
        assert config.normalize_symbol("BTC-USDT-SWAP") == "BTCUSDT"

    def test_bybit_btc_usdt(self):
        config = Config(exchange=Exchange.BYBIT)
        assert config.normalize_symbol("BTC-USDT") == "BTCUSDT"

    def test_bingx_btcusdt(self):
        config = Config(exchange=Exchange.BINGX)
        assert config.normalize_symbol("BTCUSDT") == "BTC-USDT"

    def test_bingx_btc_usdt(self):
        config = Config(exchange=Exchange.BINGX)
        assert config.normalize_symbol("BTC-USDT") == "BTC-USDT"

    def test_bingx_btc_usdt_swap(self):
        config = Config(exchange=Exchange.BINGX)
        assert config.normalize_symbol("BTC-USDT-SWAP") == "BTC-USDT-SWAP"

    def test_lowercase_input(self):
        config = Config(exchange=Exchange.OKX)
        assert config.normalize_symbol("btcusdt") == "BTC-USDT-SWAP"

    def test_underscore_input(self):
        config = Config(exchange=Exchange.OKX)
        assert config.normalize_symbol("BTC_USDT") == "BTC-USDT-SWAP"


class TestLeverageMap:
    """Test leverage config parsing."""

    def test_parse_leverage_config(self):
        config = Config(leverage_config="BTC-USDT-SWAP:50,ETH-USDT-SWAP:25")
        lev_map = config.leverage_map
        assert lev_map["BTC-USDT-SWAP"] == 50
        assert lev_map["ETH-USDT-SWAP"] == 25

    def test_get_leverage_for_symbol(self):
        config = Config(exchange=Exchange.OKX, leverage_config="BTC-USDT-SWAP:50,ETH-USDT-SWAP:25")
        assert config.get_leverage_for_symbol("BTC-USDT-SWAP") == 50
        assert config.get_leverage_for_symbol("ETH-USDT-SWAP") == 25
        assert config.get_leverage_for_symbol("SOL-USDT-SWAP") == 50  # default


class TestIntervalString:
    """Test timeframe to interval string conversion."""

    def test_okx_intervals(self):
        config = Config(exchange=Exchange.OKX)
        assert config.get_interval_string() == "15m"  # default 15min

        config.timeframe = 60
        assert config.get_interval_string() == "1H"

        config.timeframe = 240
        assert config.get_interval_string() == "4H"

        config.timeframe = 1440
        assert config.get_interval_string() == "1D"

    def test_bybit_intervals(self):
        config = Config(exchange=Exchange.BYBIT, timeframe=15)
        assert config.get_interval_string() == "15"

        config.timeframe = 60
        assert config.get_interval_string() == "60"

    def test_bingx_intervals(self):
        config = Config(exchange=Exchange.BINGX, timeframe=15)
        assert config.get_interval_string() == "15m"

        config.timeframe = 60
        assert config.get_interval_string() == "1h"


class TestPositionSizeForBalance:
    """Test position size calculation based on balance."""

    def test_position_size_100(self):
        config = Config(fixed_position_size=1.0)
        assert config.calculate_position_size_for_balance(100.0) == 1.0

    def test_position_size_200(self):
        config = Config(fixed_position_size=1.0)
        assert config.calculate_position_size_for_balance(200.0) == 2.0

    def test_position_size_350(self):
        config = Config(fixed_position_size=1.0)
        assert config.calculate_position_size_for_balance(350.0) == 3.0

    def test_position_size_below_100(self):
        config = Config(fixed_position_size=1.0)
        assert config.calculate_position_size_for_balance(50.0) == 1.0


class TestSymbolList:
    """Test symbol list property."""

    def test_symbol_list(self):
        config = Config(symbols="BTC-USDT-SWAP,ETH-USDT-SWAP")
        assert config.symbol_list == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]

    def test_symbol_alias(self):
        config = Config(symbols="BTC-USDT-SWAP")
        assert config.symbol == "BTC-USDT-SWAP"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
