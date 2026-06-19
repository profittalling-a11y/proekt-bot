"""Weex API client wrapper (stub - API docs pending)."""
import logging
from typing import Optional, Dict, List

from .exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class WeexClient(ExchangeClient):
    """Weex client stub. API documentation needed."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        logger.warning("Weex client is a stub. API documentation needed for full implementation.")

    def normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.replace("_", "-").upper()
        if "-" not in symbol and symbol.endswith("USDT"):
            base = symbol[:-4]
            symbol = f"{base}-USDT"
        return symbol

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        raise NotImplementedError("Weex API: implementation pending")

    def get_ticker_price(self, symbol: str) -> float:
        raise NotImplementedError("Weex API: implementation pending")

    def get_balance(self) -> float:
        raise NotImplementedError("Weex API: implementation pending")

    def get_position(self, symbol: str) -> Optional[Dict]:
        raise NotImplementedError("Weex API: implementation pending")

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "Market",
                    price: Optional[float] = None, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None, reduce_only: bool = False) -> Dict:
        raise NotImplementedError("Weex API: implementation pending")

    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        raise NotImplementedError("Weex API: implementation pending")

    def set_leverage(self, symbol: str, leverage: int):
        raise NotImplementedError("Weex API: implementation pending")

    def get_server_time(self) -> int:
        import time
        return int(time.time() * 1000)

    def get_exchange_info(self, symbol: str) -> Dict:
        raise NotImplementedError("Weex API: implementation pending")
