"""Account manager for multiple exchange accounts."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Account:
    """Represents a single exchange account."""

    def __init__(
        self,
        account_id: str,
        name: str,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: str = "",
        timeframe: int = 15,
        supertrend_multiplier: float = 3.0,
        trading_mode: str = "testnet",
        created_at: Optional[str] = None
    ):
        """Initialize account.

        Args:
            account_id: Unique account ID
            name: User-friendly account name
            exchange: Exchange name (okx, bybit, bingx)
            api_key: API key
            api_secret: API secret
            passphrase: API passphrase (for OKX)
            timeframe: Timeframe in minutes
            supertrend_multiplier: Supertrend multiplier
            trading_mode: Trading mode (testnet, paper, live)
            created_at: Creation timestamp
        """
        self.account_id = account_id
        self.name = name
        self.exchange = exchange
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.timeframe = timeframe
        self.supertrend_multiplier = supertrend_multiplier
        self.trading_mode = trading_mode
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert account to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "account_id": self.account_id,
            "name": self.name,
            "exchange": self.exchange,
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "passphrase": self.passphrase,
            "timeframe": self.timeframe,
            "supertrend_multiplier": self.supertrend_multiplier,
            "trading_mode": self.trading_mode,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: Dict) -> 'Account':
        """Create account from dictionary.

        Args:
            data: Dictionary with account data

        Returns:
            Account instance
        """
        return Account(
            account_id=data["account_id"],
            name=data["name"],
            exchange=data["exchange"],
            api_key=data["api_key"],
            api_secret=data["api_secret"],
            passphrase=data.get("passphrase", ""),
            timeframe=data.get("timeframe", 15),
            supertrend_multiplier=data.get("supertrend_multiplier", 3.0),
            trading_mode=data.get("trading_mode", "testnet"),
            created_at=data.get("created_at"),
        )

    def get_masked_key(self) -> str:
        """Get masked API key for display.

        Returns:
            Masked API key
        """
        if len(self.api_key) <= 8:
            return "****"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"


class AccountManager:
    """Manager for multiple exchange accounts."""

    def __init__(self, storage_path: str = "data/accounts.json"):
        """Initialize account manager.

        Args:
            storage_path: Path to accounts storage file
        """
        self.storage_path = Path(storage_path)
        self.accounts: Dict[str, Account] = {}
        self.active_account_id: Optional[str] = None

        # Create data directory if not exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load accounts
        self.load_accounts()

    def load_accounts(self):
        """Load accounts from storage."""
        if not self.storage_path.exists():
            logger.info("No accounts file found, starting fresh")
            return

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.accounts = {
                acc_id: Account.from_dict(acc_data)
                for acc_id, acc_data in data.get("accounts", {}).items()
            }

            self.active_account_id = data.get("active_account_id")

            logger.info(f"Loaded {len(self.accounts)} accounts")

        except Exception as e:
            logger.error(f"Error loading accounts: {e}")

    def save_accounts(self):
        """Save accounts to storage."""
        try:
            data = {
                "accounts": {
                    acc_id: account.to_dict()
                    for acc_id, account in self.accounts.items()
                },
                "active_account_id": self.active_account_id,
            }

            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(self.accounts)} accounts")

        except Exception as e:
            logger.error(f"Error saving accounts: {e}")
            raise

    def add_account(
        self,
        name: str,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: str = "",
        timeframe: int = 15,
        supertrend_multiplier: float = 3.0,
        trading_mode: str = "testnet"
    ) -> Account:
        """Add new account.

        Args:
            name: Account name
            exchange: Exchange name
            api_key: API key
            api_secret: API secret
            passphrase: API passphrase
            timeframe: Timeframe
            supertrend_multiplier: Supertrend multiplier
            trading_mode: Trading mode

        Returns:
            Created account

        Raises:
            ValueError: If account with same name exists
        """
        # Check if name already exists
        for account in self.accounts.values():
            if account.name == name:
                raise ValueError(f"Account with name '{name}' already exists")

        # Generate unique ID
        account_id = f"{exchange}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create account
        account = Account(
            account_id=account_id,
            name=name,
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            timeframe=timeframe,
            supertrend_multiplier=supertrend_multiplier,
            trading_mode=trading_mode,
        )

        self.accounts[account_id] = account

        # Set as active if first account
        if len(self.accounts) == 1:
            self.active_account_id = account_id

        self.save_accounts()

        logger.info(f"Added account: {name} ({exchange})")

        return account

    def remove_account(self, account_id: str) -> bool:
        """Remove account.

        Args:
            account_id: Account ID to remove

        Returns:
            True if removed, False if not found

        Raises:
            ValueError: If trying to remove active account
        """
        if account_id not in self.accounts:
            return False

        if account_id == self.active_account_id:
            raise ValueError("Cannot remove active account. Switch to another account first.")

        del self.accounts[account_id]
        self.save_accounts()

        logger.info(f"Removed account: {account_id}")

        return True

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID.

        Args:
            account_id: Account ID

        Returns:
            Account or None if not found
        """
        return self.accounts.get(account_id)

    def get_active_account(self) -> Optional[Account]:
        """Get active account.

        Returns:
            Active account or None
        """
        if self.active_account_id:
            return self.accounts.get(self.active_account_id)
        return None

    def set_active_account(self, account_id: str) -> bool:
        """Set active account.

        Args:
            account_id: Account ID to activate

        Returns:
            True if set, False if not found
        """
        if account_id not in self.accounts:
            return False

        self.active_account_id = account_id
        self.save_accounts()

        logger.info(f"Set active account: {account_id}")

        return True

    def list_accounts(self) -> List[Dict]:
        """List all accounts.

        Returns:
            List of account dictionaries (with masked keys)
        """
        accounts_list = []

        for account in self.accounts.values():
            accounts_list.append({
                "account_id": account.account_id,
                "name": account.name,
                "exchange": account.exchange,
                "api_key_masked": account.get_masked_key(),
                "timeframe": account.timeframe,
                "supertrend_multiplier": account.supertrend_multiplier,
                "trading_mode": account.trading_mode,
                "created_at": account.created_at,
                "is_active": account.account_id == self.active_account_id,
            })

        return accounts_list

    def update_account(
        self,
        account_id: str,
        name: Optional[str] = None,
        timeframe: Optional[int] = None,
        supertrend_multiplier: Optional[float] = None,
        trading_mode: Optional[str] = None
    ) -> bool:
        """Update account settings.

        Args:
            account_id: Account ID
            name: New name
            timeframe: New timeframe
            supertrend_multiplier: New multiplier
            trading_mode: New trading mode

        Returns:
            True if updated, False if not found
        """
        account = self.get_account(account_id)

        if not account:
            return False

        if name is not None:
            # Check if new name conflicts with other accounts
            for acc in self.accounts.values():
                if acc.account_id != account_id and acc.name == name:
                    raise ValueError(f"Account with name '{name}' already exists")
            account.name = name

        if timeframe is not None:
            account.timeframe = timeframe

        if supertrend_multiplier is not None:
            account.supertrend_multiplier = supertrend_multiplier

        if trading_mode is not None:
            account.trading_mode = trading_mode

        self.save_accounts()

        logger.info(f"Updated account: {account_id}")

        return True
