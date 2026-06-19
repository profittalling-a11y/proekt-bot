"""Factory for creating exchange clients."""
import logging
from typing import Optional

from .exchange_client import ExchangeClient
from .okx_client import OKXClient
from .bybit_client import BybitClient
from .bingx_client import BingXClient
from .gate_client import GateClient
from .bitget_client import BitgetClient
from .pionex_client import PionexClient
from .weex_client import WeexClient
from .toobit_client import ToobitClient

logger = logging.getLogger(__name__)


class ExchangeFactory:
    """Factory for creating exchange client instances."""

    SUPPORTED_EXCHANGES = {
        "okx": OKXClient,
        "bybit": BybitClient,
        "bingx": BingXClient,
        "gate": GateClient,
        "bitget": BitgetClient,
        "pionex": PionexClient,
        "weex": WeexClient,
        "toobit": ToobitClient,
    }

    PASSPHRASE_REQUIRED = {"okx", "bitget"}

    @staticmethod
    def create_client(
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        testnet: bool = True
    ) -> ExchangeClient:
        """Create exchange client instance.

        Args:
            exchange: Exchange name (okx, bybit, bingx, gate, bitget, pionex, weex, toobit)
            api_key: API key
            api_secret: API secret
            passphrase: API passphrase (required for OKX, Bitget)
            testnet: Use testnet/demo mode

        Returns:
            Exchange client instance

        Raises:
            ValueError: If exchange is not supported
        """
        exchange = exchange.lower()

        if exchange not in ExchangeFactory.SUPPORTED_EXCHANGES:
            raise ValueError(
                f"Unsupported exchange: {exchange}. "
                f"Supported: {', '.join(ExchangeFactory.SUPPORTED_EXCHANGES.keys())}"
            )

        client_class = ExchangeFactory.SUPPORTED_EXCHANGES[exchange]

        if exchange in ExchangeFactory.PASSPHRASE_REQUIRED:
            if not passphrase:
                raise ValueError(f"{exchange.upper()} requires passphrase parameter")
            return client_class(api_key, api_secret, passphrase, testnet)

        return client_class(api_key, api_secret, testnet)

    @staticmethod
    def get_supported_exchanges() -> list:
        """Get list of supported exchanges."""
        return list(ExchangeFactory.SUPPORTED_EXCHANGES.keys())

    @staticmethod
    def requires_passphrase(exchange: str) -> bool:
        """Check if exchange requires passphrase."""
        return exchange.lower() in ExchangeFactory.PASSPHRASE_REQUIRED
