"""OKX V5 API client wrapper with error handling and retry logic."""
import time
import logging
from typing import Optional, Dict, List, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from okx.api import API

from .exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class OKXClient(ExchangeClient):
    """Wrapper for OKX V5 API with enhanced error handling."""

    def __init__(self, api_key: str, api_secret: str, passphrase: str, testnet: bool = True):
        """Initialize OKX client.

        Args:
            api_key: OKX API key
            api_secret: OKX API secret
            passphrase: OKX API passphrase
            testnet: Use demo trading if True, live if False
        """
        super().__init__(api_key, api_secret, testnet)
        self.passphrase = passphrase

        # Set flag for demo trading
        flag = "1" if testnet else "0"  # 1 = demo, 0 = live

        # Initialize OKX API client
        self.client = API(
            key=api_key,
            secret=api_secret,
            passphrase=passphrase,
            flag=flag
        )

        # Cache for positions to reduce API calls
        self._positions_cache = {}
        self._positions_cache_time = {}
        self._cache_ttl = 5  # Cache for 5 seconds

        self._setup_session()
        logger.info(f"OKX client initialized (demo={testnet})")

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

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to OKX format.

        Args:
            symbol: Symbol in any format

        Returns:
            Symbol in OKX format (e.g., BTC-USDT-SWAP)
        """
        # Convert BTCUSDT to BTC-USDT-SWAP
        symbol = symbol.replace("_", "-").upper()

        if "-" not in symbol and symbol.endswith("USDT"):
            base = symbol[:-4]
            symbol = f"{base}-USDT-SWAP"
        elif not symbol.endswith("-SWAP"):
            symbol = f"{symbol}-SWAP"

        return symbol

    def _handle_response(self, response: Dict[str, Any]) -> Any:
        """Handle API response and check for errors.

        Args:
            response: API response dictionary

        Returns:
            Response data

        Raises:
            Exception: If API returns error
        """
        if isinstance(response, dict):
            code = response.get("code", "0")
            msg = response.get("msg", "")

            if code != "0":
                logger.error(f"API Error: {code} - {msg}")
                raise Exception(f"OKX API Error {code}: {msg}")

            return response.get("data", [])

        return response

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        """Get historical klines/candlesticks.

        Args:
            symbol: Trading pair (e.g., BTC-USDT-SWAP for perpetual)
            interval: Timeframe (1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M)
            limit: Number of candles (max 300)

        Returns:
            List of kline dictionaries with OHLCV data
        """
        try:
            symbol = self.normalize_symbol(symbol)
            response = self.client.market.get_candles(
                instId=symbol,
                bar=interval,
                limit=str(min(limit, 300))
            )

            data = self._handle_response(response)

            if not data:
                return []

            all_klines = []
            for k in data:
                all_klines.append({
                    "timestamp": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                })

            # OKX returns newest first, reverse to oldest first
            all_klines.reverse()
            logger.debug(f"Fetched {len(all_klines)} klines for {symbol}")
            return all_klines

        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            raise

    def get_ticker_price(self, symbol: str) -> float:
        """Get current ticker price.

        Args:
            symbol: Trading pair (e.g., BTC-USDT-SWAP)

        Returns:
            Current price
        """
        try:
            symbol = self.normalize_symbol(symbol)
            response = self.client.market.get_ticker(instId=symbol)
            data = self._handle_response(response)

            if not data:
                raise Exception(f"No ticker data for {symbol}")

            price = float(data[0].get("last", 0))
            logger.debug(f"Current price for {symbol}: {price}")
            return price

        except Exception as e:
            logger.error(f"Error fetching ticker price: {e}")
            raise

    def get_balance(self) -> float:
        """Get USDT balance.

        Returns:
            Available USDT balance
        """
        try:
            response = self.client.account.get_balance(ccy="USDT")
            data = self._handle_response(response)

            if not data:
                return 0.0

            details = data[0].get("details", [])
            for detail in details:
                if detail.get("ccy") == "USDT":
                    balance = float(detail.get("availBal", 0))
                    logger.debug(f"USDT balance: {balance}")
                    return balance

            return 0.0

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error fetching balance: {e}")
            logger.error("Не удается подключиться к OKX. Проверьте интернет или используйте VPN")
            return 0.0
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout fetching balance: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching balance: {e}", exc_info=True)
            return 0.0

    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for symbol.

        Args:
            symbol: Trading pair (e.g., BTC-USDT-SWAP)

        Returns:
            Position dict or None if no position
        """
        try:
            symbol = self.normalize_symbol(symbol)

            # Check cache first
            current_time = time.time()
            if symbol in self._positions_cache:
                cache_time = self._positions_cache_time.get(symbol, 0)
                if current_time - cache_time < self._cache_ttl:
                    logger.debug(f"Returning cached position for {symbol}")
                    return self._positions_cache[symbol]

            # Add delay to avoid rate limiting
            time.sleep(0.1)

            response = self.client.account.get_positions(instId=symbol)
            data = self._handle_response(response)

            position_data = None
            for pos in data:
                size = float(pos.get("pos", 0))
                if size != 0:
                    # Log raw position data from OKX
                    logger.info(f"Raw OKX position data: pos={pos.get('pos')}, posSide={pos.get('posSide')}, instId={pos.get('instId')}")

                    # Determine side based on posSide field (not pos size!)
                    pos_side = pos.get("posSide", "")
                    if pos_side == "long":
                        side = "Buy"
                    elif pos_side == "short":
                        side = "Sell"
                    else:
                        # Fallback to size-based detection
                        side = "Buy" if size > 0 else "Sell"
                        logger.warning(f"Unknown posSide '{pos_side}', using size-based detection: {side}")

                    position_data = {
                        "symbol": pos.get("instId"),
                        "side": side,
                        "size": abs(size),
                        "entry_price": float(pos.get("avgPx", 0)),
                        "unrealized_pnl": float(pos.get("upl", 0)),
                        "leverage": float(pos.get("lever", 1)),
                    }
                    logger.debug(f"Position: {position_data}")
                    break

            # Update cache
            self._positions_cache[symbol] = position_data
            self._positions_cache_time[symbol] = current_time

            return position_data

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error fetching position for {symbol}: {e}")
            logger.error("Возможные причины: 1) Проблемы с интернетом 2) OKX недоступен в вашем регионе 3) Нужен VPN")
            return None
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout fetching position for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching position for {symbol}: {e}", exc_info=True)
            return None

    def get_all_positions(self) -> List[Dict]:
        """Get all open positions.

        Returns:
            List of position dictionaries
        """
        try:
            # Get all positions without specifying symbol
            response = self.client.account.get_positions()
            data = self._handle_response(response)

            positions = []
            for pos in data:
                size = float(pos.get("pos", 0))
                if size != 0:
                    # Log raw position data from OKX
                    logger.info(f"Raw OKX position data: pos={pos.get('pos')}, posSide={pos.get('posSide')}, instId={pos.get('instId')}")

                    # Determine side based on posSide field (not pos size!)
                    pos_side = pos.get("posSide", "")
                    if pos_side == "long":
                        side = "Buy"
                    elif pos_side == "short":
                        side = "Sell"
                    else:
                        # Fallback to size-based detection
                        side = "Buy" if size > 0 else "Sell"
                        logger.warning(f"Unknown posSide '{pos_side}', using size-based detection: {side}")

                    position_data = {
                        "symbol": pos.get("instId"),
                        "side": side,
                        "size": abs(size),
                        "entry_price": float(pos.get("avgPx", 0)),
                        "unrealized_pnl": float(pos.get("upl", 0)),
                        "leverage": float(pos.get("lever", 1)),
                    }
                    positions.append(position_data)

            logger.debug(f"Found {len(positions)} open positions")
            return positions

        except Exception as e:
            logger.error(f"Error fetching all positions: {e}")
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
        """Place an order.

        Args:
            symbol: Trading pair (e.g., BTC-USDT-SWAP)
            side: Buy or Sell
            qty: Order quantity (in contracts)
            order_type: Market or Limit
            price: Limit price (for limit orders)
            stop_loss: Stop loss price
            take_profit: Take profit price
            reduce_only: Reduce only flag

        Returns:
            Order response
        """
        try:
            symbol = self.normalize_symbol(symbol)
            # Convert side to OKX format
            okx_side = "buy" if side == "Buy" else "sell"

            # Convert order type
            okx_order_type = "market" if order_type == "Market" else "limit"

            # Determine position side (long/short)
            pos_side = "long" if side == "Buy" else "short"

            # Determine trade mode
            td_mode = "cross"  # cross margin mode

            params = {
                "instId": symbol,
                "tdMode": td_mode,
                "side": okx_side,
                "posSide": pos_side,
                "ordType": okx_order_type,
                "sz": str(qty),
            }

            if price and order_type == "Limit":
                params["px"] = str(price)

            if reduce_only:
                params["reduceOnly"] = "true"

            logger.info(f"Placing order: {side} {qty} {symbol} @ {order_type}")
            response = self.client.trade.set_order(**params)
            data = self._handle_response(response)

            if not data:
                raise Exception("No response data from order placement")

            order_id = data[0].get("ordId", "")
            logger.info(f"Order placed successfully: {order_id}")

            # Place stop loss and take profit as separate orders if provided
            if stop_loss:
                self._place_stop_order(symbol, pos_side, qty, stop_loss, "stop_loss")

            if take_profit:
                self._place_stop_order(symbol, pos_side, qty, take_profit, "take_profit")

            return {"orderId": order_id, "data": data[0]}

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    def _place_stop_order(self, symbol: str, pos_side: str, qty: float, trigger_price: float, order_type: str):
        """Place stop loss or take profit order.

        Args:
            symbol: Trading pair
            pos_side: Position side (long/short)
            qty: Order quantity
            trigger_price: Trigger price
            order_type: stop_loss or take_profit
        """
        try:
            # Determine side (opposite of position)
            side = "sell" if pos_side == "long" else "buy"

            params = {
                "instId": symbol,
                "tdMode": "cross",
                "side": side,
                "posSide": pos_side,
                "ordType": "conditional",
                "sz": str(qty),
                "triggerPx": str(trigger_price),
                "orderPx": "-1",  # Market price
            }

            response = self.client.trade.place_algo_order(**params)
            self._handle_response(response)

            logger.info(f"{order_type} order placed at {trigger_price}")

        except Exception as e:
            logger.warning(f"Error placing {order_type} order: {e}")

    def close_position(self, symbol: str, side: str, qty: float) -> Dict:
        """Close position by placing opposite order.

        Args:
            symbol: Trading pair
            side: Current position side (Buy or Sell)
            qty: Position size to close

        Returns:
            Order response
        """
        symbol = self.normalize_symbol(symbol)
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
        """Set leverage for symbol.

        Args:
            symbol: Trading pair
            leverage: Leverage value (1-125)
        """
        try:
            symbol = self.normalize_symbol(symbol)
            response = self.client.account.set_leverage(
                instId=symbol,
                lever=str(leverage),
                mgnMode="cross"
            )
            self._handle_response(response)
            logger.info(f"Leverage set to {leverage}x for {symbol}")

        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            raise

    def get_server_time(self) -> int:
        """Get OKX server time.

        Returns:
            Server timestamp in milliseconds
        """
        try:
            response = self.client.public.get_system_time()
            data = self._handle_response(response)

            if data:
                return int(data[0].get("ts", 0))

            return int(time.time() * 1000)

        except Exception as e:
            logger.error(f"Error fetching server time: {e}")
            raise

    def get_exchange_info(self, symbol: str) -> Dict:
        """Get exchange information for symbol.

        Args:
            symbol: Trading pair

        Returns:
            Dictionary with symbol info
        """
        try:
            symbol = self.normalize_symbol(symbol)
            response = self.client.public.get_instruments(
                instType="SWAP",
                instId=symbol
            )
            data = self._handle_response(response)

            if not data:
                return {}

            instrument = data[0]

            return {
                "symbol": symbol,
                "min_qty": float(instrument.get("minSz", 0)),
                "max_qty": float(instrument.get("maxMktSz", 0)),
                "qty_step": float(instrument.get("lotSz", 0)),
                "price_precision": int(instrument.get("tickSz", "0.01").count("0") + 1),
                "max_leverage": float(instrument.get("lever", 125)),
            }

        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            return {}
