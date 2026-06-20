"""Integration bridge between trading bot and Hermes Agent.

Architecture:
┌─────────────────┐     HTTP      ┌─────────────────┐
│   Hermes Agent  │ ──────────▶   │  Trading Bot    │
│   (Analysis)    │               │  (Execution)    │
└─────────────────┘               └─────────────────┘
        │                                 │
        │  1. Analyze market              │
        │  2. Detect trend change         │
        │  3. Send signal ──────────────▶ │ 4. Validate
        │                                 │ 5. Execute trade
        │  ◀────────────────────────────  │ 6. Report result

Data flow:
- Hermes → Bot: POST /api/hermes/signal
- Bot → Hermes: GET /api/hermes/status
- Shared: data/hermes_state.json (trend state, positions)
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HermesSignal:
    """Signal from Hermes Agent."""
    symbol: str
    action: str  # 'buy', 'sell', 'close'
    price: float
    confidence: float  # 0.0 to 1.0
    source: str  # 'cumulative_delta', 'trend_analysis', 'pattern'
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class HermesBridge:
    """Bridge for communication between trading bot and Hermes Agent.

    Manages shared state and signal validation.
    """

    def __init__(self, state_file: str = "data/hermes_state.json"):
        """Initialize bridge.

        Args:
            state_file: Path to shared state file
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load shared state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'trend_state': {},
            'last_signals': [],
            'positions': {},
            'stats': {
                'total_signals': 0,
                'accepted_signals': 0,
                'rejected_signals': 0,
            }
        }

    def _save_state(self):
        """Save shared state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def receive_signal(self, signal: HermesSignal) -> Dict:
        """Receive and validate signal from Hermes Agent.

        Args:
            signal: Signal from Hermes

        Returns:
            Validation result
        """
        self.state['stats']['total_signals'] += 1

        # Validate signal
        is_valid, reason = self._validate_signal(signal)

        if not is_valid:
            self.state['stats']['rejected_signals'] += 1
            self._save_state()
            return {'accepted': False, 'reason': reason}

        # Accept signal
        self.state['stats']['accepted_signals'] += 1
        self.state['trend_state'][signal.symbol] = signal.action
        self.state['last_signals'].append({
            'symbol': signal.symbol,
            'action': signal.action,
            'price': signal.price,
            'confidence': signal.confidence,
            'timestamp': signal.timestamp
        })

        # Keep only last 100 signals
        self.state['last_signals'] = self.state['last_signals'][-100:]

        self._save_state()

        logger.info(f"Hermes signal accepted: {signal.action} {signal.symbol} @ {signal.price} (confidence: {signal.confidence})")

        return {'accepted': True, 'reason': 'Signal validated'}

    def _validate_signal(self, signal: HermesSignal) -> tuple:
        """Validate incoming signal.

        Rules:
        1. Minimum confidence threshold
        2. No duplicate signals within cooldown
        3. Symbol must be in active trading list

        Args:
            signal: Signal to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check confidence
        if signal.confidence < 0.5:
            return False, f"Low confidence: {signal.confidence}"

        # Check duplicate (cooldown 60 seconds)
        for prev_signal in self.state['last_signals'][-10:]:
            if (prev_signal['symbol'] == signal.symbol and
                prev_signal['action'] == signal.action and
                signal.timestamp - prev_signal['timestamp'] < 60):
                return False, "Duplicate signal within cooldown"

        return True, "OK"

    def get_trend_state(self, symbol: str) -> Optional[str]:
        """Get current trend state for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Current trend direction or None
        """
        return self.state['trend_state'].get(symbol)

    def get_stats(self) -> Dict:
        """Get signal statistics."""
        return self.state['stats']

    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """Get recent signals."""
        return self.state['last_signals'][-limit:]


# Global bridge instance
_bridge: Optional[HermesBridge] = None


def get_bridge() -> HermesBridge:
    """Get or create global bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = HermesBridge()
    return _bridge
