"""Telegram bot — approval workflow using aiogram v3.

Sends trade proposals to TELEGRAM_APPROVED_USER_ID.
Handles Approve/Reject/Details inline keyboard callbacks.
Writes ProposalApproval records on decision.

Left blank/stub when TELEGRAM_BOT_TOKEN is not set.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_APPROVED_USER_ID = int(os.getenv("TELEGRAM_APPROVED_USER_ID", "0") or "0")

# Lazy import aiogram only when token is set, to avoid import error when not installed yet.
_bot: Any = None
_dp: Any = None


def _get_bot() -> Any:
    global _bot, _dp
    if _bot is not None:
        return _bot
    if not _BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set — configure it before Phase 6")
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        _bot = Bot(token=_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        _dp = Dispatcher()
        _register_handlers(_dp)
    except ImportError:
        raise RuntimeError("aiogram not installed — add it to pyproject.toml for Phase 6")
    return _bot


def _register_handlers(dp: Any) -> None:
    from aiogram import F
    from aiogram.types import CallbackQuery

    @dp.callback_query(F.data.startswith("approve:"))
    async def handle_approve(callback: CallbackQuery) -> None:
        proposal_id = callback.data.split(":", 1)[1]
        if callback.from_user.id != _APPROVED_USER_ID:
            await callback.answer("Unauthorized.", show_alert=True)
            return
        await _record_decision(proposal_id, "approved", callback.from_user.id)
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ <b>APPROVED</b> by you."
        )
        await callback.answer("Approved!")

    @dp.callback_query(F.data.startswith("reject:"))
    async def handle_reject(callback: CallbackQuery) -> None:
        proposal_id = callback.data.split(":", 1)[1]
        if callback.from_user.id != _APPROVED_USER_ID:
            await callback.answer("Unauthorized.", show_alert=True)
            return
        await _record_decision(proposal_id, "rejected", callback.from_user.id)
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ <b>REJECTED</b> by you."
        )
        await callback.answer("Rejected.")


async def send_proposal(proposal: Any) -> bool:
    """Send a formatted trade proposal to the approver. Returns True on success."""
    if not _BOT_TOKEN or not _APPROVED_USER_ID:
        logger.warning("telegram.not_configured")
        return False

    try:
        bot = _get_bot()
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        pid = str(proposal.proposal_id)
        rr = f"{proposal.risk_reward_ratio:.1f}"
        conf = f"{proposal.confidence:.0%}"

        text = (
            f"🤖 <b>JARVIS Trade Proposal</b>\n\n"
            f"<b>Symbol:</b> {proposal.symbol} ({proposal.market.upper()})\n"
            f"<b>Direction:</b> {'📈 LONG' if proposal.direction.value == 'long' else '📉 SHORT'}\n"
            f"<b>Entry:</b> ${proposal.entry_price:,.4f}\n"
            f"<b>Stop Loss:</b> ${proposal.stop_loss:,.4f}\n"
            f"<b>Take Profit:</b> ${proposal.take_profit:,.4f}\n"
            f"<b>R:R Ratio:</b> {rr}x\n"
            f"<b>Position Size:</b> {proposal.position_size_pct:.1f}%\n"
            f"<b>Confidence:</b> {conf}\n\n"
            f"<b>Evidence:</b>\n{proposal.evidence_summary}\n\n"
            f"⏱ Expires in {proposal.expiry_seconds}s"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"approve:{pid}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{pid}"),
            ]
        ])

        await bot.send_message(_APPROVED_USER_ID, text, reply_markup=keyboard)
        logger.info("telegram.proposal_sent", symbol=proposal.symbol, proposal_id=pid)
        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("telegram.send_failed", error_type=type(exc).__name__)
        return False


async def send_notification(text: str) -> bool:
    """Send a plain notification to the approver."""
    if not _BOT_TOKEN or not _APPROVED_USER_ID:
        return False
    try:
        bot = _get_bot()
        await bot.send_message(_APPROVED_USER_ID, text)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("telegram.notify_failed", error_type=type(exc).__name__)
        return False


async def _record_decision(proposal_id: str, status: str, telegram_user_id: int) -> None:
    """Write approval record to DB."""
    try:
        from jarvis.db.base import get_session_factory
        from jarvis.execution.models import ProposalApproval
        import uuid

        async with get_session_factory()() as session:
            approval = ProposalApproval(
                proposal_id=uuid.UUID(proposal_id),
                telegram_user_id=telegram_user_id,
                status=status,
                decided_at=datetime.now(UTC),
            )
            session.add(approval)
            await session.commit()
        logger.info("telegram.decision_recorded", proposal_id=proposal_id, status=status)
    except Exception as exc:  # noqa: BLE001
        logger.error("telegram.db_write_failed", error_type=type(exc).__name__)


async def start_polling() -> None:
    """Start the bot polling loop (call from worker process)."""
    if not _BOT_TOKEN:
        logger.warning("telegram.polling_skipped", reason="TELEGRAM_BOT_TOKEN not set")
        return
    bot = _get_bot()
    logger.info("telegram.polling_start")
    await _dp.start_polling(bot)
