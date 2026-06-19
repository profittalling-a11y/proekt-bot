"""BingX API client wrapper with error handling and retry logic."""
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


class BingXClient(ExchangeClient):
    """Wrapper for BingX API with enhanced error handling."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """Initialize BingX client.

        Args:
            api_key: BingX API key
            api_secret: BingX API secret
            testnet: Use demo if True, live if False
        """
        super().__init__(api_key, api_secret, testnet)

        # BingX uses same URL for demo and live, demo is determined by account type
        self.base_url = "https://open-api.bingx.com"

        self._setup_session()
        logger.info(f"BingX client initialized (demo={testnet})")

    def _setup_session(self):
        """Setup requests session with retry logic."""
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _generate_signature(self, params: str) -> str:
        """Generate signature for BingX API."""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _send_request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """Send request to BingX API."""
        if params is None:
            params = {}

        # Add timestamp
        params['timestamp'] = int(time.time() * 1000)

        # Create query string
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])

        # Generate signature
        signature = self._generate_signature(query_string)
        params['signature'] = signature

        # Set headers
        headers = {
            'X-BX-APIKEY': self.api_key,
        }

        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                response = self.session.get(url, params=params, headers=headers, timeout=10)
            else:
                response = self.session.post(url, params=params, headers=headers, timeout=10)

            response.raise_for_status()
            data = response.json()

            if data.get('code') != 0:
                raise Exception(f"BingX API Error {data.get('code')}: {data.get('msg')}")

            return data.get('data', {})

        except Exception as e:
            logger.error(f"Request error: {e}")
            raise

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to BingX format.

        Args:
            symbol: Symbol in any format

        Returns:
            Symbol in BingX format (e.g., BTC-USDT)
        """
        # BingX uses dash format
        symbol = symbol.replace("_", "-").upper()

        # Convert BTCUSDT to BTC-USDT
        if "-" not in symbol and symbol.endswith("USDT"):
            base = symbol[:-4]
            symbol = f"{base}-USDT"

        return symbol

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        """Get historical klines/candlesticks."""
        try:
            # BingX interval format: 1m, 5m, 15m, 30m, 1h, 4h, 1d
            interval = interval.lower().replace("m", "m").replace("h", "h")

            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': min(limit, 1000)
            }

            data = self._send_request("GET", "/openApi/swap/v2/quote/klines", params)

            klines = []
            for k in data:
                klines.append({
                    "timestamp": int(k['time']),
                    "open": float(k['open']),
                    "high": float(k['high']),
                    "low": float(k['low']),
                    "close": float(k['close']),
                    "volume": float(k['volume']),
                })

            logger.debug(f"Fetched {len(klines)} klines for {symbol}")
            return klines

        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            raise

    def get_ticker_price(self, symbol: str) -> float:
        """Get current ticker price."""
        try:
            params = {'symbol': symbol}
            data = self._send_request("GET", "/openApi/swap/v2/quote/price", params)

            price = float(data.get('price', 0))
            logger.debug(f"Current price for {symbol}: {price}")
            return price

        except Exception as e:
            logger.error(f"Error fetching ticker price: {e}")
            raise

    def get_balance(self) -> float:
        """Get USDT balance."""
        try:
            data = self._send_request("GET", "/openApi/swap/v2/user/balance", {})

            balance_data = data.get('balance', {})
            balance = float(balance_data.get('availableMargin', 0))

            logger.debug(f"USDT balance: {balance}")
            return balance

        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            raise

    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for symbol."""
        try:
            params = {'symbol': symbol}
            data = self._send_request("GET", "/openApi/swap/v2/user/positions", params)

            if not data:
                return None

            for pos in data:
                if pos.get('symbol') == symbol:
                    position_size = float(pos.get('positionAmt', 0))

                    if position_size == 0:
                        continue

                    side = "Buy" if position_size > 0 else "Sell"

                    position_data = {
                        "symbol": symbol,
                        "side": side,
                        "size": abs(position_size),
                        "entry_price": float(pos.get('avgPrice', 0)),
                        "unrealized_pnl": float(pos.get('unrealizedProfit', 0)),
                        "leverage": float(pos.get('leverage', 1)),
                    }
                    logger.debug(f"Position: {position_data}")
                    return position_data

            return None

        except Exception as e:
            logger.error(f"Error fetching position: {e}")
            raise

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
        """Place an order."""
        try:
            # Convert side to BingX format
            bingx_side = "BUY" if side == "Buy" else "SELL"

            # Determine position side
            position_side = "LONG" if side == "Buy" else "SHORT"

            params = {
                'symbol': symbol,
                'side': bingx_side,
                'positionSide': position_side,
                'type': 'MARKET' if order_type == "Market" else 'LIMIT',
                'quantity': qty,
            }

            if price and order_type == "Limit":
                params['price'] = price

            if reduce_only:
                params['reduceOnly'] = 'true'

            logger.info(f"Placing order: {side} {qty} {symbol} @ {order_type}")
            data = self._send_request("POST", "/openApi/swap/v2/trade/order", params)

            order_id = data.get('order', {}).get('orderId', '')
            logger.info(f"Order placed successfully: {order_id}")

            # Place stop loss and take profit as separate orders if provided
            if stop_loss:
                self._place_stop_order(symbol, position_side, qty, stop_loss, "STOP_MARKET")

            if take_profit:
                self._place_stop_order(symbol, position_side, qty, take_profit, "TAKE_PROFIT_MARKET")

            return {"orderId": order_id, "data": data}

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    def _place_stop_order(self, symbol: str, position_side: str, qty: float, stop_price: float, order_type: str):
        """Place stop loss or take profit order."""
        try:
            # Opposite side for closing
            side = "SELL" if position_side == "LONG" else "BUY"

            params = {
                'symbol': symbol,
                'side': side,
                'positionSide': position_side,
                'type': order_type,
                'quantity': qty,
                'stopPrice': stop_price,
            }

            self._send_request("POST", "/openApi/swap/v2/trade/order", params)
            logger.info(f"{order_type} order placed at {stop_price}")

        except Exception as e:
            logger.warning(f"Error placing {order_type} order: {e}")

    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        """Close position by placing opposite order."""
        close_side = "Sell" if side == "Buy" else "Buy"
        logger.info(f"Closing position: {side} {qty} {symbol}")

        return self.place_order(
            symbol=symbol,
            side=close_side,
            qty=qty,
            order_type="Market",
            reduce_only=True
        )

    def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for symbol."""
        try:
            params = {
                'symbol': symbol,
                'side': 'LONG',
                'leverage': leverage
            }
            self._send_request("POST", "/openApi/swap/v2/trade/leverage", params)

            params['side'] = 'SHORT'
            self._send_request("POST", "/openApi/swap/v2/trade/leverage", params)

            logger.info(f"Leverage set to {leverage}x for {symbol}")

        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            raise

    def get_server_time(self) -> int:
        """Get BingX server time."""
        try:
            response = self.session.get(f"{self.base_url}/openApi/swap/v2/server/time", timeout=10)
            data = response.json()
            return int(data.get('data', {}).get('serverTime', 0))

        except Exception as e:
            logger.error(f"Error fetching server time: {e}")
            return int(time.time() * 1000)

    def get_exchange_info(self, symbol: str) -> Dict:
        """Get exchange information for symbol."""
        try:
            params = {'symbol': symbol}
            data = self._send_request("GET", "/openApi/swap/v2/quote/contracts", params)

            if not data:
                return {}

            return {
                "symbol": symbol,
                "min_qty": float(data.get('minQty', 0)),
                "max_qty": float(data.get('maxQty', 0)),
                "qty_step": float(data.get('stepSize', 0)),
                "price_precision": int(data.get('pricePrecision', 2)),
                "max_leverage": float(data.get('maxLeverage', 125)),
            }

        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            return {}
