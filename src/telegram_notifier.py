"""Telegram notifications module."""
import logging
import requests
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications to Telegram."""

    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        """Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
            enabled: Enable/disable notifications
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

        if self.enabled:
            logger.info(f"Telegram notifier initialized for chat {chat_id}")
        else:
            logger.info("Telegram notifier disabled")

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram.

        Args:
            text: Message text
            parse_mode: Parse mode (HTML or Markdown)

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.debug("Telegram disabled, skipping message")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }

            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()

            logger.debug("Telegram message sent successfully")
            return True

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def notify_position_opened(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        leverage: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ):
        """Notify about opened position.

        Args:
            symbol: Trading symbol
            direction: LONG or SHORT
            entry_price: Entry price
            quantity: Position quantity
            leverage: Leverage used
            stop_loss: Stop loss price
            take_profit: Take profit price
        """
        direction_emoji = "🟢" if direction.upper() == "LONG" else "🔴"

        text = f"""
{direction_emoji} <b>Позиция открыта</b>

<b>Тикер:</b> {symbol}
<b>Направление:</b> {direction.upper()}
<b>Цена входа:</b> ${entry_price:,.2f}
<b>Количество:</b> {quantity:.8f}
<b>Плечо:</b> {leverage}x
"""

        if stop_loss:
            text += f"<b>Stop Loss:</b> ${stop_loss:,.2f}\n"

        if take_profit:
            text += f"<b>Take Profit:</b> ${take_profit:,.2f}\n"

        text += f"\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"

        self.send_message(text)

    def notify_position_closed(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        pnl: float,
        pnl_percent: float,
        reason: str = "signal"
    ):
        """Notify about closed position.

        Args:
            symbol: Trading symbol
            direction: LONG or SHORT
            entry_price: Entry price
            exit_price: Exit price
            quantity: Position quantity
            pnl: Profit/loss in USDT
            pnl_percent: Profit/loss in percentage
            reason: Close reason
        """
        if pnl >= 0:
            result_emoji = "✅"
            result_text = "Прибыль"
        else:
            result_emoji = "❌"
            result_text = "Убыток"

        direction_emoji = "🟢" if direction.upper() == "LONG" else "🔴"

        text = f"""
{result_emoji} <b>Позиция закрыта</b>

<b>Тикер:</b> {symbol}
<b>Направление:</b> {direction_emoji} {direction.upper()}
<b>Цена входа:</b> ${entry_price:,.2f}
<b>Цена выхода:</b> ${exit_price:,.2f}
<b>Количество:</b> {quantity:.8f}

<b>{result_text}:</b> ${pnl:,.2f} ({pnl_percent:+.2f}%)
<b>Причина:</b> {reason}

<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""

        self.send_message(text)

    def notify_daily_summary(
        self,
        balance: float,
        daily_pnl: float,
        daily_pnl_percent: float,
        daily_trades: int,
        open_positions: int
    ):
        """Send daily summary.

        Args:
            balance: Current balance
            daily_pnl: Daily PnL
            daily_pnl_percent: Daily PnL percentage
            daily_trades: Number of trades today
            open_positions: Number of open positions
        """
        emoji = "📊"

        text = f"""
{emoji} <b>Дневной отчет</b>

<b>Баланс:</b> ${balance:,.2f}
<b>Дневной PnL:</b> ${daily_pnl:,.2f} ({daily_pnl_percent:+.2f}%)
<b>Сделок сегодня:</b> {daily_trades}
<b>Открытых позиций:</b> {open_positions}

<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""

        self.send_message(text)

    def notify_error(self, error_message: str):
        """Notify about error.

        Args:
            error_message: Error message
        """
        text = f"""
⚠️ <b>Ошибка</b>

{error_message}

<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""

        self.send_message(text)

    def notify_bot_started(self):
        """Notify that bot started."""
        text = """
🚀 <b>Бот запущен</b>

Торговый бот успешно запущен и готов к работе.
"""
        self.send_message(text)

    def notify_bot_stopped(self, reason: str = "manual"):
        """Notify that bot stopped.

        Args:
            reason: Stop reason
        """
        text = f"""
🛑 <b>Бот остановлен</b>

Причина: {reason}

<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
        self.send_message(text)

    def test_connection(self) -> bool:
        """Test Telegram connection.

        Returns:
            True if connection successful
        """
        return self.send_message("✅ Telegram подключен успешно!")
