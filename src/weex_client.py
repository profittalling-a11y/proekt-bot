"""Weex API v3 client wrapper."""
import time
import hmac
import hashlib
import base64
import logging
from typing import Optional, Dict, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class WeexClient(ExchangeClient):
    """Wrapper for Weex API v3."""

    def __init__(self, api_key: str, api_secret: str, passphrase: str = "", testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        self.passphrase = passphrase
        if testnet:
            self.base_url = "https://api-testnet.weex.com/api/swap/v3"
        else:
            self.base_url = "https://api.weex.com/api/swap/v3"
        self._setup_session()
        logger.info(f"Weex client initialized (testnet={testnet})")

    def _setup_session(self):
        self.session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(self.api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(signature).decode("utf-8")

    def _send_request(self, method: str, endpoint: str, params: Dict = None, body: Dict = None) -> Dict:
        timestamp = str(int(time.time() * 1000))
        path = endpoint
        body_str = str(body) if body else ""
        sign = self._sign(timestamp, method.upper(), path, body_str)

        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{endpoint}"
        if method == "GET":
            resp = self.session.get(url, params=params, headers=headers, timeout=10)
        else:
            resp = self.session.post(url, json=body, headers=headers, timeout=10)

        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"Weex API Error: {data.get('msg')}")
        return data.get("data", {})

    def normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.replace("_", "-").upper()
        if "-" not in symbol and symbol.endswith("USDT"):
            base = symbol[:-4]
            symbol = f"{base}-USDT"
        return symbol

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        symbol = self.normalize_symbol(symbol)
        interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1D"}
        weex_interval = interval_map.get(interval, interval)
        data = self._send_request("GET", "/market/kline", {"symbol": symbol, "interval": weex_interval, "limit": str(limit)})
        return [
            {"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]),
             "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
            for k in reversed(data) if isinstance(k, list)
        ]

    def get_ticker_price(self, symbol: str) -> float:
        symbol = self.normalize_symbol(symbol)
        data = self._send_request("GET", "/market/ticker", {"symbol": symbol})
        return float(data.get("last", 0))

    def get_balance(self) -> float:
        data = self._send_request("GET", "/account/balance")
        if isinstance(data, list):
            for item in data:
                if item.get("currency") == "USDT":
                    return float(item.get("available", 0))
        return 0.0

    def get_position(self, symbol: str) -> Optional[Dict]:
        symbol = self.normalize_symbol(symbol)
        try:
            data = self._send_request("GET", "/position/list", {"symbol": symbol})
            if isinstance(data, list):
                for pos in data:
                    size = float(pos.get("positionAmt", 0))
                    if size != 0:
                        return {
                            "symbol": symbol,
                            "side": "Buy" if pos.get("positionSide") == "LONG" else "Sell",
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
            data = self._send_request("GET", "/position/list")
            positions = []
            if isinstance(data, list):
                for pos in data:
                    size = float(pos.get("positionAmt", 0))
                    if size != 0:
                        positions.append({
                            "symbol": pos.get("symbol"),
                            "side": "Buy" if pos.get("positionSide") == "LONG" else "Sell",
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
            "positionSide": "LONG" if side == "Buy" else "SHORT",
        }
        if price and order_type == "Limit":
            body["price"] = str(price)
        if reduce_only:
            body["reduceOnly"] = True
        data = self._send_request("POST", "/order/place", body=body)
        return {"orderId": data.get("orderId"), "data": data}

    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        symbol = self.normalize_symbol(symbol)
        close_side = "Sell" if side == "Buy" else "Buy"
        return self.place_order(symbol, close_side, qty, "Market", reduce_only=True)

    def set_leverage(self, symbol: str, leverage: int):
        symbol = self.normalize_symbol(symbol)
        self._send_request("POST", "/position/leverage", {"symbol": symbol, "leverage": str(leverage)})

    def get_server_time(self) -> int:
        data = self._send_request("GET", "/market/time")
        return int(data.get("serverTime", time.time() * 1000))

    def get_exchange_info(self, symbol: str) -> Dict:
        symbol = self.normalize_symbol(symbol)
        data = self._send_request("GET", "/market/instruments", {"symbol": symbol})
        if isinstance(data, list) and data:
            instrument = data[0]
            return {
                "symbol": symbol,
                "min_qty": float(instrument.get("minQty", 0)),
                "max_qty": float(instrument.get("maxQty", 0)),
                "qty_step": float(instrument.get("stepSize", 0)),
                "price_precision": int(instrument.get("pricePrecision", 2)),
                "max_leverage": float(instrument.get("maxLeverage", 100)),
            }
        return {}
