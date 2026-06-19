"""Gate.io API v4 client wrapper."""
import time
import hmac
import hashlib
import logging
from typing import Optional, Dict, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class GateClient(ExchangeClient):
    """Wrapper for Gate.io API v4."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        if testnet:
            self.base_url = "https://api-testnet.gateapi.io/api/v4"
        else:
            self.base_url = "https://api.gateio.ws/api/v4"
        self._setup_session()
        logger.info(f"Gate.io client initialized (testnet={testnet})")

    def _setup_session(self):
        self.session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _sign(self, method: str, url: str, query: str = "", payload: str = "") -> Dict:
        t = str(int(time.time()))
        m = hashlib.sha512()
        m.update(payload.encode("utf-8"))
        hashed = m.hexdigest()
        sign_str = f"{method}\n{url}\n{query}\n{hashed}\n{t}"
        sign = hmac.new(self.api_secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha512).hexdigest()
        return {"KEY": self.api_key, "Timestamp": t, "SIGN": sign, "Content-Type": "application/json"}

    def _send_request(self, method: str, endpoint: str, params: Dict = None, body: Dict = None) -> Dict:
        query = "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else ""
        payload = str(body) if body else ""
        url = f"{self.base_url}{endpoint}"
        headers = self._sign(method, endpoint, query, payload)

        if method == "GET":
            resp = self.session.get(url, params=params, headers=headers, timeout=10)
        else:
            resp = self.session.post(url, json=body, headers=headers, timeout=10)

        resp.raise_for_status()
        return resp.json()

    def normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.replace("_", "-").upper()
        if "-" not in symbol and symbol.endswith("USDT"):
            base = symbol[:-4]
            symbol = f"{base}_USDT"
        elif not symbol.endswith("_USDT"):
            if symbol.endswith("-USDT"):
                symbol = symbol.replace("-USDT", "_USDT")
            elif not symbol.endswith("_USDT"):
                symbol = f"{symbol}_USDT"
        return symbol

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        symbol = self.normalize_symbol(symbol)
        interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1d"}
        gate_interval = interval_map.get(interval, interval)
        data = self._send_request("GET", "/futures/usdt/candlesticks", {"contract": symbol, "interval": gate_interval, "limit": limit})
        return [
            {"timestamp": int(k["t"]) * 1000, "open": float(k["o"]), "high": float(k["h"]),
             "low": float(k["l"]), "close": float(k["c"]), "volume": float(k["v"])}
            for k in reversed(data)
        ]

    def get_ticker_price(self, symbol: str) -> float:
        symbol = self.normalize_symbol(symbol)
        data = self._send_request("GET", "/futures/usdt/tickers", {"contract": symbol})
        return float(data[0]["last"]) if data else 0.0

    def get_balance(self) -> float:
        data = self._send_request("GET", "/futures/usdt/accounts")
        return float(data.get("available", 0))

    def get_position(self, symbol: str) -> Optional[Dict]:
        symbol = self.normalize_symbol(symbol)
        try:
            data = self._send_request("GET", "/futures/usdt/positions")
            for pos in data:
                if pos.get("contract") == symbol and float(pos.get("size", 0)) != 0:
                    size = float(pos["size"])
                    return {
                        "symbol": symbol,
                        "side": "Buy" if size > 0 else "Sell",
                        "size": abs(size),
                        "entry_price": float(pos.get("entry_price", 0)),
                        "unrealized_pnl": float(pos.get("unrealised_pnl", 0)),
                        "leverage": float(pos.get("leverage", 1)),
                    }
            return None
        except Exception as e:
            logger.error(f"Error fetching position: {e}")
            return None

    def get_all_positions(self) -> List[Dict]:
        try:
            data = self._send_request("GET", "/futures/usdt/positions")
            positions = []
            for pos in data:
                size = float(pos.get("size", 0))
                if size != 0:
                    positions.append({
                        "symbol": pos.get("contract"),
                        "side": "Buy" if size > 0 else "Sell",
                        "size": abs(size),
                        "entry_price": float(pos.get("entry_price", 0)),
                        "unrealized_pnl": float(pos.get("unrealised_pnl", 0)),
                        "leverage": float(pos.get("leverage", 1)),
                    })
            return positions
        except Exception as e:
            logger.error(f"Error fetching all positions: {e}")
            return []

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "Market",
                    price: Optional[float] = None, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None, reduce_only: bool = False) -> Dict:
        symbol = self.normalize_symbol(symbol)
        body = {
            "contract": symbol,
            "size": int(qty) if side == "Buy" else -int(qty),
            "price": str(price) if price and order_type == "Limit" else "0",
            "tif": "ioc" if order_type == "Market" else "gtc",
        }
        if reduce_only:
            body["reduce_only"] = True
        data = self._send_request("POST", "/futures/usdt/orders", body=body)
        return {"orderId": data.get("id"), "data": data}

    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        symbol = self.normalize_symbol(symbol)
        close_side = "Sell" if side == "Buy" else "Buy"
        return self.place_order(symbol, close_side, qty, "Market", reduce_only=True)

    def set_leverage(self, symbol: str, leverage: int):
        symbol = self.normalize_symbol(symbol)
        self._send_request("POST", "/futures/usdt/positions/leverage", body={"contract": symbol, "leverage": str(leverage)})

    def get_server_time(self) -> int:
        return int(time.time() * 1000)

    def get_exchange_info(self, symbol: str) -> Dict:
        symbol = self.normalize_symbol(symbol)
        data = self._send_request("GET", f"/futures/usdt/contracts/{symbol}")
        return {
            "symbol": symbol,
            "min_qty": float(data.get("quanto_multiplier", 1)),
            "max_qty": float(data.get("max_size", 0)),
            "qty_step": float(data.get("quanto_multiplier", 1)),
            "price_precision": 2,
            "max_leverage": float(data.get("max_leverage", 100)),
        }
