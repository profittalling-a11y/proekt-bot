"""Pionex API client - NOT AVAILABLE.

Pionex does not provide a public REST API for third-party bots.
Their platform is closed-source with API only for internal use.

Use Bybit or OKX instead for automated trading.
"""
import logging
from typing import Optional, Dict, List

from .exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class PionexClient(ExchangeClient):
    """Pionex client stub - API not available."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        logger.warning("Pionex: No public API available. Use Bybit or OKX instead.")

    def normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.replace("_", "").replace("-", "").upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        return symbol

    def _not_available(self):
        raise NotImplementedError("Pionex has no public API for third-party bots. Use Bybit or OKX.")

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        self._not_available()

    def get_ticker_price(self, symbol: str) -> float:
        self._not_available()

    def get_balance(self) -> float:
        self._not_available()

    def get_position(self, symbol: str) -> Optional[Dict]:
        self._not_available()

    def get_all_positions(self) -> List[Dict]:
        self._not_available()

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "Market",
                    price: Optional[float] = None, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None, reduce_only: bool = False) -> Dict:
        self._not_available()

    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        self._not_available()

    def set_leverage(self, symbol: str, leverage: int):
        self._not_available()

    def get_server_time(self) -> int:
        import time
        return int(time.time() * 1000)

    def get_exchange_info(self, symbol: str) -> Dict:
        self._not_available()
