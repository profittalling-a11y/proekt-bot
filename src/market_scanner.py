"""Market scanner for finding liquid trading pairs."""
import logging
from typing import List, Dict
import okx.MarketData as MarketData
import okx.PublicData as PublicData

logger = logging.getLogger(__name__)


class MarketScanner:
    """Scan OKX markets for liquid trading pairs."""

    def __init__(self, api_key: str, api_secret: str, passphrase: str, testnet: bool = True):
        """Initialize market scanner.

        Args:
            api_key: OKX API key
            api_secret: OKX API secret
            passphrase: OKX API passphrase
            testnet: Use demo trading if True
        """
        flag = "1" if testnet else "0"  # 1 = demo, 0 = live

        self.market_api = MarketData.MarketAPI(api_key, api_secret, passphrase, False, flag)
        self.public_api = PublicData.PublicAPI(api_key, api_secret, passphrase, False, flag)
        self.testnet = testnet
        logger.info(f"Market scanner initialized (demo={testnet})")

    def get_liquid_pairs(
        self,
        min_volume_usdt: float = 1_000_000,
        quote_currency: str = "USDT",
        inst_type: str = "SWAP"
    ) -> List[Dict]:
        """Get liquid trading pairs based on 24h volume.

        Args:
            min_volume_usdt: Minimum 24h volume in USDT (default 1M)
            quote_currency: Quote currency (default USDT)
            inst_type: Instrument type (SWAP for perpetual futures)

        Returns:
            List of liquid pairs with their info
        """
        try:
            logger.info(f"Scanning markets with min volume ${min_volume_usdt:,.0f}...")

            # Get all tickers for SWAP instruments
            response = self.market_api.get_tickers(instType=inst_type)

            if response.get("code") != "0":
                logger.error(f"API Error: {response.get('msg')}")
                return []

            tickers = response.get("data", [])

            liquid_pairs = []

            for ticker in tickers:
                inst_id = ticker.get("instId", "")

                # Filter by quote currency (e.g., BTC-USDT-SWAP)
                if f"-{quote_currency}-" not in inst_id:
                    continue

                # Get 24h volume in quote currency (USDT)
                volume_24h_ccy = float(ticker.get("volCcy24h", 0))

                # Filter by minimum volume
                if volume_24h_ccy < min_volume_usdt:
                    continue

                # Get other info
                last_price = float(ticker.get("last", 0))

                # Calculate 24h price change percentage
                open_24h = float(ticker.get("open24h", 0))
                if open_24h > 0:
                    price_change_percent = ((last_price - open_24h) / open_24h) * 100
                else:
                    price_change_percent = 0.0

                liquid_pairs.append({
                    "symbol": inst_id,
                    "volume_24h": volume_24h_ccy,
                    "last_price": last_price,
                    "price_change_24h": price_change_percent,
                })

            # Sort by volume (highest first)
            liquid_pairs.sort(key=lambda x: x["volume_24h"], reverse=True)

            logger.info(f"Found {len(liquid_pairs)} liquid pairs")

            # Log top 10
            for i, pair in enumerate(liquid_pairs[:10], 1):
                logger.info(
                    f"{i}. {pair['symbol']}: "
                    f"${pair['volume_24h']:,.0f} volume, "
                    f"${pair['last_price']:,.2f} price, "
                    f"{pair['price_change_24h']:+.2f}% change"
                )

            return liquid_pairs

        except Exception as e:
            logger.error(f"Error scanning markets: {e}", exc_info=True)
            return []

    def get_symbol_leverage_info(self, symbol: str) -> Dict:
        """Get leverage information for a symbol.

        Args:
            symbol: Trading symbol (e.g., BTC-USDT-SWAP)

        Returns:
            Dictionary with leverage info
        """
        try:
            response = self.public_api.get_instruments(
                instType="SWAP",
                instId=symbol
            )

            if response.get("code") != "0":
                logger.error(f"API Error: {response.get('msg')}")
                return {}

            instruments = response.get("data", [])

            if not instruments:
                return {}

            instrument = instruments[0]

            max_leverage = float(instrument.get("lever", 125))

            return {
                "symbol": symbol,
                "max_leverage": int(max_leverage),
                "min_leverage": 1,
            }

        except Exception as e:
            logger.error(f"Error getting leverage info for {symbol}: {e}")
            return {}

    def build_leverage_config(self, symbols: List[str]) -> str:
        """Build leverage configuration string for multiple symbols.

        Args:
            symbols: List of trading symbols

        Returns:
            Leverage config string (e.g., "BTC-USDT-SWAP:50,ETH-USDT-SWAP:50")
        """
        config_parts = []

        for symbol in symbols:
            leverage_info = self.get_symbol_leverage_info(symbol)

            if leverage_info:
                max_lev = leverage_info["max_leverage"]
                # Cap at 50x for safety
                leverage = min(max_lev, 50)
                config_parts.append(f"{symbol}:{leverage}")

        return ",".join(config_parts)

    def get_top_liquid_symbols(
        self,
        limit: int = 10,
        min_volume_usdt: float = 1_000_000
    ) -> List[str]:
        """Get top N liquid symbols.

        Args:
            limit: Number of symbols to return
            min_volume_usdt: Minimum 24h volume

        Returns:
            List of symbol names
        """
        liquid_pairs = self.get_liquid_pairs(min_volume_usdt=min_volume_usdt)
        return [pair["symbol"] for pair in liquid_pairs[:limit]]

    def scan_and_configure(
        self,
        max_symbols: int = 10,
        min_volume_usdt: float = 1_000_000
    ) -> Dict:
        """Scan markets and generate configuration.

        Args:
            max_symbols: Maximum number of symbols to trade
            min_volume_usdt: Minimum 24h volume

        Returns:
            Dictionary with symbols and leverage config
        """
        logger.info("=" * 60)
        logger.info("MARKET SCANNER")
        logger.info(f"Min Volume: ${min_volume_usdt:,.0f}")
        logger.info(f"Max Symbols: {max_symbols}")
        logger.info("=" * 60)

        # Get liquid pairs
        liquid_pairs = self.get_liquid_pairs(min_volume_usdt=min_volume_usdt)

        if not liquid_pairs:
            logger.warning("No liquid pairs found!")
            return {"symbols": [], "leverage_config": ""}

        # Take top N
        top_pairs = liquid_pairs[:max_symbols]
        symbols = [pair["symbol"] for pair in top_pairs]

        # Build leverage config
        logger.info("Building leverage configuration...")
        leverage_config = self.build_leverage_config(symbols)

        logger.info("=" * 60)
        logger.info("CONFIGURATION GENERATED")
        logger.info(f"Symbols: {','.join(symbols)}")
        logger.info(f"Leverage Config: {leverage_config}")
        logger.info("=" * 60)

        return {
            "symbols": symbols,
            "symbols_str": ",".join(symbols),
            "leverage_config": leverage_config,
            "pairs_info": top_pairs,
        }


def scan_markets(api_key: str, api_secret: str, passphrase: str, testnet: bool = True, exchange: str = "okx") -> Dict:
    """Convenience function to scan markets.

    Args:
        api_key: API key
        api_secret: API secret
        passphrase: API passphrase
        testnet: Use demo trading
        exchange: Exchange name (currently only OKX supported)

    Returns:
        Configuration dictionary
    """
    if exchange != "okx":
        logger.warning(f"Market scanning not supported for {exchange}, using manual configuration")
        return {"symbols": [], "symbols_str": "", "leverage_config": ""}

    scanner = MarketScanner(api_key, api_secret, passphrase, testnet)
    return scanner.scan_and_configure(max_symbols=10, min_volume_usdt=1_000_000)
