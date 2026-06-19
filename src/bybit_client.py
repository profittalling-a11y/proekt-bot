"""Bybit V5 API client wrapper with error handling and retry logic."""
import logging
from typing import Optional, Dict, List, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pybit.unified_trading import HTTP

from .exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class BybitClient(ExchangeClient):
    """Wrapper for Bybit V5 API with enhanced error handling."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """Initialize Bybit client.

        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            testnet: Use testnet if True, mainnet if False
        """
        super().__init__(api_key, api_secret, testnet)

        self.client = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret,
        )

        self._setup_session()
        logger.info(f"Bybit client initialized (testnet={testnet})")

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

    def _handle_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Handle API response and check for errors."""
        ret_code = response.get("retCode", -1)
        ret_msg = response.get("retMsg", "Unknown error")

        if ret_code != 0:
            logger.error(f"API Error: {ret_code} - {ret_msg}")
            raise Exception(f"Bybit API Error {ret_code}: {ret_msg}")

        return response.get("result", {})

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to Bybit format.

        Args:
            symbol: Symbol in any format

        Returns:
            Symbol in Bybit format (e.g., BTCUSDT)
        """
        # Remove dashes and convert to uppercase
        symbol = symbol.replace("-", "").replace("_", "").upper()

        # Ensure it ends with USDT
        if not symbol.endswith("USDT"):
            symbol = symbol + "USDT"

        return symbol

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        """Get historical klines/candlesticks."""
        try:
            # Normalize interval to Bybit format
            interval = interval.replace("m", "").replace("M", "").replace("h", "").replace("H", "")

            response = self.client.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            result = self._handle_response(response)

            klines = []
            for k in result.get("list", []):
                klines.append({
                    "timestamp": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                })

            # Bybit returns newest first, reverse to oldest first
            klines.reverse()
            logger.debug(f"Fetched {len(klines)} klines for {symbol}")
            return klines

        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            raise

    def get_ticker_price(self, symbol: str) -> float:
        """Get current ticker price."""
        try:
            response = self.client.get_tickers(
                category="linear",
                symbol=symbol
            )
            result = self._handle_response(response)

            ticker_list = result.get("list", [])
            if not ticker_list:
                raise Exception(f"No ticker data for {symbol}")

            price = float(ticker_list[0].get("lastPrice", 0))
            logger.debug(f"Current price for {symbol}: {price}")
            return price

        except Exception as e:
            logger.error(f"Error fetching ticker price: {e}")
            raise

    def get_balance(self) -> float:
        """Get USDT balance."""
        try:
            response = self.client.get_wallet_balance(
                accountType="UNIFIED"
            )
            result = self._handle_response(response)

            coins = result.get("list", [{}])[0].get("coin", [])
            for coin in coins:
                if coin.get("coin") == "USDT":
                    balance = float(coin.get("availableToWithdraw", 0))
                    logger.debug(f"USDT balance: {balance}")
                    return balance

            return 0.0

        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            raise

    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for symbol."""
        try:
            response = self.client.get_positions(
                category="linear",
                symbol=symbol
            )
            result = self._handle_response(response)

            positions = result.get("list", [])
            for pos in positions:
                size = float(pos.get("size", 0))
                if size > 0:
                    position_data = {
                        "symbol": pos.get("symbol"),
                        "side": pos.get("side"),
                        "size": size,
                        "entry_price": float(pos.get("avgPrice", 0)),
                        "unrealized_pnl": float(pos.get("unrealisedPnl", 0)),
                        "leverage": float(pos.get("leverage", 1)),
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
            params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": str(qty),
                "reduceOnly": reduce_only,
            }

            if price and order_type == "Limit":
                params["price"] = str(price)

            if stop_loss:
                params["stopLoss"] = str(stop_loss)

            if take_profit:
                params["takeProfit"] = str(take_profit)

            logger.info(f"Placing order: {side} {qty} {symbol} @ {order_type}")
            response = self.client.place_order(**params)
            result = self._handle_response(response)

            logger.info(f"Order placed successfully: {result.get('orderId')}")
            return result

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

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
            response = self.client.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            self._handle_response(response)
            logger.info(f"Leverage set to {leverage}x for {symbol}")

        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            raise

    def get_server_time(self) -> int:
        """Get Bybit server time."""
        try:
            response = self.client.get_server_time()
            result = self._handle_response(response)
            return int(result.get("timeSecond", 0)) * 1000

        except Exception as e:
            logger.error(f"Error fetching server time: {e}")
            raise

    def get_exchange_info(self, symbol: str) -> Dict:
        """Get exchange information for symbol."""
        try:
            response = self.client.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            result = self._handle_response(response)

            instruments = result.get("list", [])
            if not instruments:
                return {}

            instrument = instruments[0]

            return {
                "symbol": symbol,
                "min_qty": float(instrument.get("lotSizeFilter", {}).get("minOrderQty", 0)),
                "max_qty": float(instrument.get("lotSizeFilter", {}).get("maxOrderQty", 0)),
                "qty_step": float(instrument.get("lotSizeFilter", {}).get("qtyStep", 0)),
                "price_precision": int(instrument.get("priceScale", 2)),
                "max_leverage": float(instrument.get("leverageFilter", {}).get("maxLeverage", 100)),
            }

        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            return {}
