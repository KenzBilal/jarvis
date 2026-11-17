"""Paper broker — simulates order execution without touching Binance.

Fills at the mid-price of the best bid/ask snapshot.
Writes immutable Order + Fill + Position records.
Re-validates risk immediately before simulated fill.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.contracts import RiskVerdict, TradeProposal
from jarvis.risk.engine import RiskContext, evaluate

logger = structlog.get_logger(__name__)

# Starting paper balance in USDT (configurable via env later)
PAPER_BALANCE_USDT = 10_000.0


async def execute_paper_trade(
    proposal: TradeProposal,
    risk_ctx: RiskContext,
    current_price: float,
    session: AsyncSession,
) -> dict:
    """
    Execute a paper trade:
    1. Re-validate risk immediately before fill.
    2. Compute position quantity from size_pct and balance.
    3. Write Order → Fill → Position (immutable audit trail).
    Returns summary dict.
    """
    # Re-validate risk (invariant: always revalidate before execution)
    result = evaluate(proposal, risk_ctx)
    if result.verdict != RiskVerdict.PASS:
        logger.warning(
            "paper_broker.risk_recheck_failed",
            symbol=proposal.symbol,
            reason=result.reason,
        )
        return {"status": "rejected", "reason": result.reason}

    # Check proposal hasn't expired
    now = datetime.now(UTC)
    created = proposal.created_at
    if (now - created).total_seconds() > proposal.expiry_seconds:
        logger.warning("paper_broker.proposal_expired", symbol=proposal.symbol)
        return {"status": "rejected", "reason": "proposal expired"}

    # Compute quantity
    balance = PAPER_BALANCE_USDT
    notional = balance * (proposal.position_size_pct / 100.0)
    quantity = notional / current_price if current_price > 0 else 0.0
    if quantity <= 0:
        return {"status": "rejected", "reason": "invalid quantity"}

    client_order_id = f"paper-{proposal.proposal_id.hex[:16]}"

    from jarvis.execution.models import Fill, Order, Position

    order = Order(
        proposal_id=proposal.proposal_id,
        client_order_id=client_order_id,
        symbol=proposal.symbol,
        market=proposal.market,
        side="buy" if proposal.direction.value == "long" else "sell",
        order_type="market",
        quantity=quantity,
        price=current_price,
        status="filled",
        is_paper=True,
    )
    session.add(order)
    await session.flush()

    fill = Fill(
        order_id=order.id,
        fill_price=current_price,
        fill_quantity=quantity,
        commission=notional * 0.001,  # 0.1% simulated fee
        commission_asset="USDT",
        filled_at=now,
    )
    session.add(fill)

    position = Position(
        symbol=proposal.symbol,
        market=proposal.market,
        direction=proposal.direction.value,
        entry_price=current_price,
        quantity=quantity,
        stop_loss=proposal.stop_loss,
        take_profit=proposal.take_profit,
        unrealized_pnl=0.0,
        is_open=True,
        is_paper=True,
        opened_at=now,
    )
    session.add(position)
    await session.flush()

    logger.info(
        "paper_broker.filled",
        symbol=proposal.symbol,
        direction=proposal.direction.value,
        price=current_price,
        quantity=round(quantity, 6),
        order_id=str(order.id),
    )

    return {
        "status": "filled",
        "order_id": str(order.id),
        "client_order_id": client_order_id,
        "symbol": proposal.symbol,
        "direction": proposal.direction.value,
        "price": current_price,
        "quantity": quantity,
        "notional_usdt": notional,
        "position_id": str(position.id),
    }
