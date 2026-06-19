"""Risk management module."""
import logging
import time
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages trading risk and position sizing."""

    def __init__(
        self,
        fixed_position_size: float = 1.0,
        risk_per_position: float = 2.0,
        max_positions: int = 10,
        max_daily_loss: float = 20.0,
        cooldown_after_loss: int = 300,
        min_balance: float = 100.0
    ):
        """Initialize risk manager.

        Args:
            fixed_position_size: Fixed position size in USDT (scales with balance)
            risk_per_position: Risk percentage per position (for stop loss calculation)
            max_positions: Maximum number of open positions
            max_daily_loss: Maximum daily loss percentage
            cooldown_after_loss: Cooldown period after loss (seconds)
            min_balance: Minimum required balance
        """
        self.fixed_position_size = fixed_position_size
        self.risk_per_position = risk_per_position
        self.max_positions = max_positions
        self.max_daily_loss = max_daily_loss
        self.cooldown_after_loss = cooldown_after_loss
        self.min_balance = min_balance

        # Track daily performance
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset_date = datetime.now().date()

        # Track losses per symbol
        self.last_loss_time: Dict[str, float] = {}
        self.consecutive_losses: Dict[str, int] = {}

        # Starting balance for daily loss calculation
        self.starting_balance = None

        # Track open positions count
        self.open_positions_count = 0

        logger.info(
            f"Risk manager initialized: fixed_size={fixed_position_size} USDT, "
            f"risk={risk_per_position}%, max_positions={max_positions}"
        )

    def reset_daily_stats(self):
        """Reset daily statistics."""
        today = datetime.now().date()
        if today > self.last_reset_date:
            logger.info(
                f"Daily reset: PnL={self.daily_pnl:.2f}, Trades={self.daily_trades}"
            )
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset_date = today
            self.starting_balance = None

    def can_trade(self, balance: float, symbol: str = "", current_positions: int = 0) -> tuple[bool, str]:
        """Check if trading is allowed based on risk rules.

        Args:
            balance: Current account balance
            symbol: Trading symbol (optional)
            current_positions: Number of currently open positions (optional)

        Returns:
            Tuple of (can_trade, reason)
        """
        self.reset_daily_stats()

        # Set starting balance if not set
        if self.starting_balance is None:
            self.starting_balance = balance

        # Check minimum balance
        if balance < self.min_balance:
            return False, f"Balance {balance:.2f} below minimum {self.min_balance}"

        # Check maximum positions
        if current_positions >= self.max_positions:
            return False, f"Maximum positions reached: {current_positions}/{self.max_positions}"

        # Check daily loss limit
        daily_loss_pct = (self.daily_pnl / self.starting_balance) * 100
        if daily_loss_pct <= -self.max_daily_loss:
            return False, f"Daily loss limit reached: {daily_loss_pct:.2f}%"

        # Check cooldown after loss for this symbol
        if symbol and symbol in self.last_loss_time:
            time_since_loss = time.time() - self.last_loss_time[symbol]
            if time_since_loss < self.cooldown_after_loss:
                remaining = int(self.cooldown_after_loss - time_since_loss)
                return False, f"Cooldown active for {symbol}: {remaining}s remaining"

        return True, "OK"

    def calculate_position_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss: float,
        leverage: int
    ) -> float:
        """Calculate position size based on fixed sizing with balance scaling.

        Logic:
        - Base position size: 1 USDT margin (configurable)
        - Scales with balance: every 100 USDT adds 1x multiplier
        - With leverage, notional value = margin * leverage

        Examples:
          * 100 USDT balance, 1 USDT margin, 50x leverage:
            - Margin: 1 USDT
            - Notional: 1 * 50 = 50 USDT
            - At BTC 50,000: 50 / 50,000 = 0.001 BTC

          * 200 USDT balance, 2 USDT margin, 50x leverage:
            - Margin: 2 USDT
            - Notional: 2 * 50 = 100 USDT
            - At BTC 50,000: 100 / 50,000 = 0.002 BTC

        Args:
            balance: Account balance
            entry_price: Entry price
            stop_loss: Stop loss price
            leverage: Leverage to use

        Returns:
            Position size in USDT (notional value)
        """
        # Calculate margin based on balance
        balance_multiplier = int(balance / 100)
        if balance_multiplier < 1:
            balance_multiplier = 1

        margin_usdt = self.fixed_position_size * balance_multiplier

        # Calculate notional value with leverage
        notional_usdt = margin_usdt * leverage

        logger.info(
            f"Position size calculation: "
            f"Margin={margin_usdt:.2f} USDT, "
            f"Notional={notional_usdt:.2f} USDT @ {leverage}x "
            f"(balance multiplier: {balance_multiplier}x)"
        )

        return notional_usdt

    def calculate_stop_loss_distance(self, entry_price: float) -> float:
        """Calculate stop loss distance based on risk percentage.

        Args:
            entry_price: Entry price

        Returns:
            Stop loss distance in price units
        """
        # Risk 2% from entry price
        distance = entry_price * (self.risk_per_position / 100)
        return distance

    def record_trade(self, pnl: float, symbol: str = ""):
        """Record trade result and update statistics.

        Args:
            pnl: Profit/loss from trade
            symbol: Trading symbol (optional)
        """
        self.daily_pnl += pnl
        self.daily_trades += 1

        if pnl < 0:
            # Record loss for this symbol
            if symbol:
                if symbol not in self.consecutive_losses:
                    self.consecutive_losses[symbol] = 0
                self.consecutive_losses[symbol] += 1
                self.last_loss_time[symbol] = time.time()

                logger.warning(
                    f"Loss recorded for {symbol}: {pnl:.2f} "
                    f"(consecutive losses: {self.consecutive_losses[symbol]})"
                )
            else:
                logger.warning(f"Loss recorded: {pnl:.2f}")
        else:
            # Reset consecutive losses on profit
            if symbol and symbol in self.consecutive_losses:
                self.consecutive_losses[symbol] = 0
            logger.info(f"Profit recorded{f' for {symbol}' if symbol else ''}: {pnl:.2f}")

        logger.info(
            f"Daily stats: PnL={self.daily_pnl:.2f}, Trades={self.daily_trades}"
        )

    def get_daily_stats(self) -> dict:
        """Get daily trading statistics.

        Returns:
            Dictionary with daily stats
        """
        daily_loss_pct = 0.0
        if self.starting_balance and self.starting_balance > 0:
            daily_loss_pct = (self.daily_pnl / self.starting_balance) * 100

        # Get max consecutive losses across all symbols
        max_consecutive_losses = max(self.consecutive_losses.values()) if self.consecutive_losses else 0

        return {
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'daily_loss_pct': daily_loss_pct,
            'starting_balance': self.starting_balance,
            'open_positions': self.open_positions_count,
            'max_positions': self.max_positions,
            'consecutive_losses': max_consecutive_losses,
        }

    def validate_order(
        self,
        balance: float,
        position_size_usdt: float,
        entry_price: float
    ) -> tuple[bool, str]:
        """Validate order before execution.

        Args:
            balance: Current balance
            position_size_usdt: Position size in USDT
            entry_price: Entry price

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if position size exceeds balance
        if position_size_usdt > balance:
            return False, f"Insufficient balance: need {position_size_usdt:.2f}, have {balance:.2f}"

        # Check minimum position size
        if position_size_usdt < 1.0:
            return False, f"Position size too small: {position_size_usdt:.2f} USDT"

        return True, "OK"

    def update_position_count(self, count: int):
        """Update open positions count.

        Args:
            count: Number of open positions
        """
        self.open_positions_count = count
