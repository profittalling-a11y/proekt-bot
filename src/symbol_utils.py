"""Symbol format registry for all exchanges.

Each exchange has its own format for futures trading pairs:
- OKX:      BTC-USDT-SWAP
- Bybit:    BTCUSDT
- BingX:    BTC-USDT
- Gate.io:  BTC_USDT
- Bitget:   BTCUSDT
- Pionex:   (no public API)
- Weex:     BTC-USDT
- Toobit:   BTCUSDT
"""
from .config import Exchange


# Canonical format: BTC-USDT-SWAP (OKX style)
# This is the INTERNAL format used throughout the bot

SYMBOL_FORMATS = {
    Exchange.OKX: {
        "suffix": "-SWAP",
        "separator": "-",
        "example": "BTC-USDT-SWAP",
    },
    Exchange.BYBIT: {
        "suffix": "",
        "separator": "",
        "example": "BTCUSDT",
    },
    Exchange.BINGX: {
        "suffix": "",
        "separator": "-",
        "example": "BTC-USDT",
    },
    Exchange.GATE: {
        "suffix": "",
        "separator": "_",
        "example": "BTC_USDT",
    },
    Exchange.BITGET: {
        "suffix": "",
        "separator": "",
        "example": "BTCUSDT",
    },
    Exchange.PIONEX: {
        "suffix": "",
        "separator": "",
        "example": "BTCUSDT",
    },
    Exchange.WEEX: {
        "suffix": "",
        "separator": "-",
        "example": "BTC-USDT",
    },
    Exchange.TOOBIT: {
        "suffix": "",
        "separator": "",
        "example": "BTCUSDT",
    },
}


def normalize_symbol(symbol: str, exchange: Exchange) -> str:
    """Normalize symbol to exchange-specific format.

    Accepts any common format:
    - BTCUSDT, BTC-USDT, BTC-USDT-SWAP, BTC_USDT

    Returns:
        Symbol in exchange-specific format
    """
    # First, extract base currency before any normalization
    s = symbol.upper().strip()

    # Remove known suffixes first
    s = s.replace("-SWAP", "").replace("_SWAP", "")

    # Now strip separators to get raw: BTCUSDT
    raw = s.replace("-", "").replace("_", "")

    # Extract base currency (everything before USDT)
    if raw.endswith("USDT"):
        base_currency = raw[:-4]
    else:
        base_currency = raw

    fmt = SYMBOL_FORMATS[exchange]

    # Build exchange-specific format
    if fmt["separator"]:
        result = f"{base_currency}{fmt['separator']}USDT"
    else:
        result = f"{base_currency}USDT"

    # Add suffix (e.g., -SWAP for OKX)
    if fmt["suffix"]:
        result += fmt["suffix"]

    return result


def to_canonical(symbol: str, exchange: Exchange) -> str:
    """Convert exchange-specific symbol to canonical format (BTC-USDT-SWAP).

    Args:
        symbol: Symbol in any exchange format
        exchange: Source exchange

    Returns:
        Symbol in canonical format
    """
    s = symbol.upper().strip()
    s = s.replace("-SWAP", "").replace("_SWAP", "")
    raw = s.replace("-", "").replace("_", "")

    if raw.endswith("USDT"):
        base_currency = raw[:-4]
    else:
        base_currency = raw

    return f"{base_currency}-USDT-SWAP"


# Common trading pairs for futures
FUTURES_PAIRS = [
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
    "BNB-USDT-SWAP",
    "XRP-USDT-SWAP",
    "ADA-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "AVAX-USDT-SWAP",
    "LINK-USDT-SWAP",
    "DOT-USDT-SWAP",
    "MATIC-USDT-SWAP",
    "UNI-USDT-SWAP",
    "ATOM-USDT-SWAP",
    "LTC-USDT-SWAP",
    "NEAR-USDT-SWAP",
    "FIL-USDT-SWAP",
]
