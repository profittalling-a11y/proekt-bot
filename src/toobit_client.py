"""Toobit API client wrapper (Binance-compatible pattern)."""
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


class ToobitClient(ExchangeClient):
    """Wrapper for Toobit API.

    Toobit uses Binance-compatible API patterns.
    API documentation: https://www.toobit.com/en-US/docs/api
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        if testnet:
            self.base_url = "https://api-testnet.toobit.com"
        else:
            self.base_url = "https://api.toobit.com"
        self._setup_session()
        logger.info(f"Toobit client initialized (testnet={testnet})")

    def _setup_session(self):
        self.session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _sign(self, params: str) -> str:
        return hmac.new(self.api_secret.encode("utf-8"), params.encode("utf-8"), hashlib.sha256).hexdigest()

    def _send_request(self, method: str, endpoint: str, params: Dict = None, body: Dict = None) -> Dict:
        params = params or {}
        params["timestamp"] = str(int(time.time() * 1000))
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = self._sign(query_string)
        params["signature"] = signature

        headers = {"X-MBX-APIKEY": self.api_key}
        url = f"{self.base_url}{endpoint}"

        if method == "GET":
            resp = self.session.get(url, params=params, headers=headers, timeout=10)
        else:
            resp = self.session.post(url, params=params, headers=headers, timeout=10)

        resp.raise_for_status()
        data = resp.json()
        if data.get("code") and data["code"] != 200:
            raise Exception(f"Toobit API Error: {data.get('msg', data)}")
        return data.get("data", data)

    def normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.replace("_", "").replace("-", "").upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        return symbol

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        symbol = self.normalize_symbol(symbol)
        interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1d"}
        toobit_interval = interval_map.get(interval, interval)
        data = self._send_request("GET", "/fapi/v1/klines", {"symbol": symbol, "interval": toobit_interval, "limit": str(limit)})
        return [
            {"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]),
             "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
            for k in data
        ]

    def get_ticker_price(self, symbol: str) -> float:
        symbol = self.normalize_symbol(symbol)
        data = self._send_request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(data.get("price", 0))

    def get_balance(self) -> float:
        data = self._send_request("GET", "/fapi/v2/balance")
        if isinstance(data, list):
            for item in data:
                if item.get("asset") == "USDT":
                    return float(item.get("availableBalance", 0))
        return 0.0

    def get_position(self, symbol: str) -> Optional[Dict]:
        symbol = self.normalize_symbol(symbol)
        try:
            data = self._send_request("GET", "/fapi/v2/positionRisk", {"symbol": symbol})
            if isinstance(data, list):
                for pos in data:
                    size = float(pos.get("positionAmt", 0))
                    if size != 0:
                        return {
                            "symbol": symbol,
                            "side": "Buy" if size > 0 else "Sell",
                            "size": abs(size),
                            "entry_price": float(pos.get("entryPrice", 0)),
                            "unrealized_pnl": float(pos.get("unRealizedProfit", 0)),
                            "leverage": float(pos.get("leverage", 1)),
                        }
            return None
        except Exception as e:
            logger.error(f"Error fetching position: {e}")
            return None

    def get_all_positions(self) -> List[Dict]:
        try:
            data = self._send_request("GET", "/fapi/v2/positionRisk")
            positions = []
            if isinstance(data, list):
                for pos in data:
                    size = float(pos.get("positionAmt", 0))
                    if size != 0:
                        positions.append({
                            "symbol": pos.get("symbol"),
                            "side": "Buy" if size > 0 else "Sell",
                            "size": abs(size),
                            "entry_price": float(pos.get("entryPrice", 0)),
                            "unrealized_pnl": float(pos.get("unRealizedProfit", 0)),
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
            "symbol": symbol,
            "side": "BUY" if side == "Buy" else "SELL",
            "type": "MARKET" if order_type == "Market" else "LIMIT",
            "quantity": str(qty),
        }
        if price and order_type == "Limit":
            body["price"] = str(price)
            body["timeInForce"] = "GTC"
        if reduce_only:
            body["reduceOnly"] = "true"
        data = self._send_request("POST", "/fapi/v1/order", body=body)
        return {"orderId": data.get("orderId"), "data": data}

    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        symbol = self.normalize_symbol(symbol)
        close_side = "Sell" if side == "Buy" else "Buy"
        return self.place_order(symbol, close_side, qty, "Market", reduce_only=True)

    def set_leverage(self, symbol: str, leverage: int):
        symbol = self.normalize_symbol(symbol)
        self._send_request("POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": str(leverage)})

    def get_server_time(self) -> int:
        data = self._send_request("GET", "/fapi/v1/time")
        return int(data.get("serverTime", time.time() * 1000))

    def get_exchange_info(self, symbol: str) -> Dict:
        symbol = self.normalize_symbol(symbol)
        data = self._send_request("GET", "/fapi/v1/exchangeInfo")
        if isinstance(data, dict):
            for s in data.get("symbols", []):
                if s.get("symbol") == symbol:
                    return {
                        "symbol": symbol,
                        "min_qty": float(s.get("filters", [{}])[0].get("minQty", 0)),
                        "max_qty": float(s.get("filters", [{}])[0].get("maxQty", 0)),
                        "qty_step": float(s.get("filters", [{}])[0].get("stepSize", 0)),
                        "price_precision": int(s.get("pricePrecision", 2)),
                        "max_leverage": 125,
                    }
        return {}
