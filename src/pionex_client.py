"""Pionex API client wrapper (limited - uses Binance engine)."""
import logging
from typing import Optional, Dict, List

from .exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class PionexClient(ExchangeClient):
    """Pionex client. Note: Pionex has limited public API."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        logger.warning("Pionex has limited API support. Consider using Binance-compatible endpoints.")

    def normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.replace("_", "").replace("-", "").upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        return symbol

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        raise NotImplementedError("Pionex API: get_klines not fully supported")

    def get_ticker_price(self, symbol: str) -> float:
        raise NotImplementedError("Pionex API: get_ticker_price not fully supported")

    def get_balance(self) -> float:
        raise NotImplementedError("Pionex API: get_balance not fully supported")

    def get_position(self, symbol: str) -> Optional[Dict]:
        raise NotImplementedError("Pionex API: get_position not fully supported")

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "Market",
                    price: Optional[float] = None, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None, reduce_only: bool = False) -> Dict:
        raise NotImplementedError("Pionex API: place_order not fully supported")

    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        raise NotImplementedError("Pionex API: close_position not fully supported")

    def set_leverage(self, symbol: str, leverage: int):
        raise NotImplementedError("Pionex API: set_leverage not fully supported")

    def get_server_time(self) -> int:
        import time
        return int(time.time() * 1000)

    def get_exchange_info(self, symbol: str) -> Dict:
        raise NotImplementedError("Pionex API: get_exchange_info not fully supported")
