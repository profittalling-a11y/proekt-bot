"""Trade history and statistics tracking."""
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Trade:
    """Trade data structure."""
    id: str
    symbol: str
    direction: TradeDirection
    status: TradeStatus
    entry_price: float
    entry_time: str
    size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    exit_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class TradeHistory:
    """Manages trade history and statistics."""

    def __init__(self, history_file: str = "data/trade_history.json"):
        """Initialize trade history.

        Args:
            history_file: Path to history file
        """
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        self.trades: List[Trade] = []
        self.load_history()

    def load_history(self):
        """Load trade history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.trades = [
                        Trade(**trade) for trade in data.get('trades', [])
                    ]
                logger.info(f"Loaded {len(self.trades)} trades from history")
            except Exception as e:
                logger.error(f"Error loading trade history: {e}")
                self.trades = []
        else:
            self.trades = []

    def save_history(self):
        """Save trade history to file."""
        try:
            data = {
                'trades': [trade.to_dict() for trade in self.trades],
                'last_updated': datetime.now().isoformat()
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Trade history saved")
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")

    def add_trade(
        self,
        trade_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Trade:
        """Add new trade to history.

        Args:
            trade_id: Unique trade ID
            symbol: Trading symbol
            direction: Trade direction (long/short)
            entry_price: Entry price
            size: Position size
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Created trade object
        """
        trade = Trade(
            id=trade_id,
            symbol=symbol,
            direction=TradeDirection(direction.lower()),
            status=TradeStatus.OPEN,
            entry_price=entry_price,
            entry_time=datetime.now().isoformat(),
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        self.trades.append(trade)
        self.save_history()
        logger.info(f"Trade added: {trade_id} {direction} {symbol} @ {entry_price}")
        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str = "manual"
    ) -> Optional[Trade]:
        """Close existing trade.

        Args:
            trade_id: Trade ID to close
            exit_price: Exit price
            exit_reason: Reason for exit

        Returns:
            Closed trade object or None
        """
        for trade in self.trades:
            if trade.id == trade_id and trade.status == TradeStatus.OPEN:
                trade.status = TradeStatus.CLOSED
                trade.exit_price = exit_price
                trade.exit_time = datetime.now().isoformat()
                trade.exit_reason = exit_reason

                # Calculate PnL
                if trade.direction == TradeDirection.LONG:
                    trade.pnl = (exit_price - trade.entry_price) * trade.size
                else:
                    trade.pnl = (trade.entry_price - exit_price) * trade.size

                trade.pnl_percent = (trade.pnl / (trade.entry_price * trade.size)) * 100

                self.save_history()
                logger.info(
                    f"Trade closed: {trade_id} PnL={trade.pnl:.2f} ({trade.pnl_percent:.2f}%)"
                )
                return trade

        logger.warning(f"Trade not found or already closed: {trade_id}")
        return None

    def get_open_trades(self) -> List[Trade]:
        """Get all open trades.

        Returns:
            List of open trades
        """
        return [t for t in self.trades if t.status == TradeStatus.OPEN]

    def get_closed_trades(self, limit: int = 50) -> List[Trade]:
        """Get recent closed trades.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of closed trades
        """
        closed = [t for t in self.trades if t.status == TradeStatus.CLOSED]
        return sorted(closed, key=lambda x: x.exit_time or "", reverse=True)[:limit]

    def get_statistics(self) -> Dict:
        """Calculate trading statistics.

        Returns:
            Dictionary with statistics
        """
        closed_trades = [t for t in self.trades if t.status == TradeStatus.CLOSED]

        if not closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
            }

        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl < 0]

        total_pnl = sum(t.pnl for t in closed_trades)
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))

        return {
            'total_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0,
            'total_pnl': total_pnl,
            'avg_win': (total_wins / len(winning_trades)) if winning_trades else 0,
            'avg_loss': (total_losses / len(losing_trades)) if losing_trades else 0,
            'profit_factor': (total_wins / total_losses) if total_losses > 0 else 0,
            'largest_win': max((t.pnl for t in winning_trades), default=0),
            'largest_loss': min((t.pnl for t in losing_trades), default=0),
        }

    def get_daily_pnl(self) -> List[Dict]:
        """Get daily PnL data for chart.

        Returns:
            List of daily PnL entries
        """
        closed_trades = [t for t in self.trades if t.status == TradeStatus.CLOSED and t.exit_time]

        daily_pnl = {}
        for trade in closed_trades:
            date = trade.exit_time.split('T')[0]
            if date not in daily_pnl:
                daily_pnl[date] = 0.0
            daily_pnl[date] += trade.pnl

        # Convert to cumulative
        cumulative = 0.0
        result = []
        for date in sorted(daily_pnl.keys()):
            cumulative += daily_pnl[date]
            result.append({
                'date': date,
                'pnl': daily_pnl[date],
                'cumulative': cumulative
            })

        return result

    def get_weekly_stats(self, starting_balance: float = 100.0) -> Dict:
        """Get weekly statistics.

        Args:
            starting_balance: Starting balance for percentage calculation

        Returns:
            Dictionary with weekly stats
        """
        from datetime import datetime, timedelta

        # Get trades from last 7 days
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        week_ago_str = week_ago.isoformat()

        weekly_trades = [
            t for t in self.trades
            if t.status == TradeStatus.CLOSED and t.exit_time and t.exit_time >= week_ago_str
        ]

        if not weekly_trades:
            return {
                'weekly_pnl': 0.0,
                'weekly_pnl_percent': 0.0,
                'weekly_trades': 0,
                'weekly_win_rate': 0.0,
            }

        weekly_pnl = sum(t.pnl for t in weekly_trades)
        weekly_pnl_percent = (weekly_pnl / starting_balance) * 100 if starting_balance > 0 else 0

        winning_trades = [t for t in weekly_trades if t.pnl > 0]
        win_rate = (len(winning_trades) / len(weekly_trades) * 100) if weekly_trades else 0

        return {
            'weekly_pnl': weekly_pnl,
            'weekly_pnl_percent': weekly_pnl_percent,
            'weekly_trades': len(weekly_trades),
            'weekly_win_rate': win_rate,
        }
