"""Abstract base class for exchange clients."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class ExchangeClient(ABC):
    """Abstract base class for cryptocurrency exchange clients."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """Initialize exchange client.

        Args:
            api_key: Exchange API key
            api_secret: Exchange API secret
            testnet: Use testnet/demo if True, live if False
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.exchange_name = self.__class__.__name__.replace("Client", "")

    @abstractmethod
    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        """Get historical klines/candlesticks.

        Args:
            symbol: Trading pair
            interval: Timeframe
            limit: Number of candles

        Returns:
            List of kline dictionaries with OHLCV data
        """
        pass

    @abstractmethod
    def get_ticker_price(self, symbol: str) -> float:
        """Get current ticker price.

        Args:
            symbol: Trading pair

        Returns:
            Current price
        """
        pass

    @abstractmethod
    def get_balance(self) -> float:
        """Get USDT balance.

        Returns:
            Available USDT balance
        """
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for symbol.

        Args:
            symbol: Trading pair

        Returns:
            Position dict or None if no position
        """
        pass

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "Market",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reduce_only: bool = False
    ) -> Dict:
        """Place an order.

        Args:
            symbol: Trading pair
            side: Buy or Sell
            qty: Order quantity
            order_type: Market or Limit
            price: Limit price (for limit orders)
            stop_loss: Stop loss price
            take_profit: Take profit price
            reduce_only: Reduce only flag

        Returns:
            Order response
        """
        pass

    @abstractmethod
    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        """Close position by placing opposite order.

        Args:
            symbol: Trading pair
            side: Current position side (Buy or Sell)
            qty: Position size to close

        Returns:
            Order response
        """
        pass

    @abstractmethod
    def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for symbol.

        Args:
            symbol: Trading pair
            leverage: Leverage value
        """
        pass

    @abstractmethod
    def get_server_time(self) -> int:
        """Get exchange server time.

        Returns:
            Server timestamp in milliseconds
        """
        pass

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to exchange format.

        Args:
            symbol: Symbol in standard format (e.g., BTCUSDT)

        Returns:
            Symbol in exchange-specific format
        """
        pass

    @abstractmethod
    def get_exchange_info(self, symbol: str) -> Dict:
        """Get exchange information for symbol.

        Args:
            symbol: Trading pair

        Returns:
            Dictionary with symbol info (min qty, price precision, etc.)
        """
        pass

    def format_quantity(self, qty: float, symbol: str) -> float:
        """Format quantity according to exchange rules.

        Args:
            qty: Raw quantity
            symbol: Trading pair

        Returns:
            Formatted quantity
        """
        # Default implementation - can be overridden
        return round(qty, 8)

    def format_price(self, price: float, symbol: str) -> float:
        """Format price according to exchange rules.

        Args:
            price: Raw price
            symbol: Trading pair

        Returns:
            Formatted price
        """
        # Default implementation - can be overridden
        return round(price, 2)
