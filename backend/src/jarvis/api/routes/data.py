"""FastAPI routers for agent runs, proposals, risk, positions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.base import get_session

router = APIRouter(prefix="/api/v1", tags=["data"])


# ------------------------------------------------------------------ #
# Agent Runs
# ------------------------------------------------------------------ #

class AgentRunOut(BaseModel):
    id: uuid.UUID
    agent_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/agent-runs", response_model=list[AgentRunOut])
async def list_agent_runs(
    session: Annotated[AsyncSession, Depends(get_session)],
    agent_type: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> list[AgentRunOut]:
    from jarvis.agents.models import AgentRun

    stmt = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)
    if agent_type:
        stmt = stmt.where(AgentRun.agent_type == agent_type)
    result = await session.execute(stmt)
    return [AgentRunOut.model_validate(r) for r in result.scalars().all()]


@router.get("/agent-runs/{run_id}/report")
async def get_agent_report(
    run_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    from jarvis.agents.models import AgentReport
    from jarvis.core.errors import NotFoundError

    result = await session.execute(select(AgentReport).where(AgentReport.run_id == run_id))
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError(details={"run_id": str(run_id)})
    return {"run_id": str(run_id), "agent_type": report.agent_type, "payload": report.payload}


# ------------------------------------------------------------------ #
# Symbols
# ------------------------------------------------------------------ #

class SymbolOut(BaseModel):
    id: uuid.UUID
    symbol: str
    base_asset: str
    quote_asset: str
    market: str
    is_active: bool
    volume_24h_usdt: float | None
    price_change_pct_24h: float | None
    last_price: float | None

    model_config = {"from_attributes": True}


@router.get("/symbols", response_model=list[SymbolOut])
async def list_symbols(
    session: Annotated[AsyncSession, Depends(get_session)],
    market: str | None = Query(None),
    limit: int = Query(100, le=500),
) -> list[SymbolOut]:
    from jarvis.market.models import TradingSymbol
    from sqlalchemy import desc

    stmt = select(TradingSymbol).where(TradingSymbol.is_active == True).order_by(
        desc(TradingSymbol.volume_24h_usdt)
    ).limit(limit)
    if market:
        stmt = stmt.where(TradingSymbol.market == market)
    result = await session.execute(stmt)
    return [SymbolOut.model_validate(r) for r in result.scalars().all()]


# ------------------------------------------------------------------ #
# Proposals
# ------------------------------------------------------------------ #

class ProposalOut(BaseModel):
    id: uuid.UUID
    symbol: str
    market: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    confidence: float
    evidence_summary: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/proposals", response_model=list[ProposalOut])
async def list_proposals(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, le=200),
) -> list[ProposalOut]:
    from jarvis.execution.models import TradeProposal

    result = await session.execute(
        select(TradeProposal).order_by(TradeProposal.created_at.desc()).limit(limit)
    )
    return [ProposalOut.model_validate(r) for r in result.scalars().all()]


# ------------------------------------------------------------------ #
# Positions
# ------------------------------------------------------------------ #

class PositionOut(BaseModel):
    id: uuid.UUID
    symbol: str
    market: str
    direction: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    unrealized_pnl: float
    is_open: bool
    is_paper: bool
    opened_at: datetime

    model_config = {"from_attributes": True}


@router.get("/positions", response_model=list[PositionOut])
async def list_positions(
    session: Annotated[AsyncSession, Depends(get_session)],
    open_only: bool = Query(True),
) -> list[PositionOut]:
    from jarvis.execution.models import Position

    stmt = select(Position).order_by(Position.opened_at.desc())
    if open_only:
        stmt = stmt.where(Position.is_open == True)
    result = await session.execute(stmt)
    return [PositionOut.model_validate(r) for r in result.scalars().all()]


# ------------------------------------------------------------------ #
# Portfolio snapshot
# ------------------------------------------------------------------ #

@router.get("/portfolio/latest")
async def get_latest_portfolio(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    from jarvis.execution.models import PortfolioSnapshot

    result = await session.execute(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_at.desc()).limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return {"message": "No portfolio snapshots yet"}
    return {
        "total_value_usdt": snap.total_value_usdt,
        "unrealized_pnl": snap.unrealized_pnl,
        "daily_pnl": snap.daily_pnl,
        "open_positions": snap.open_positions,
        "is_paper": snap.is_paper,
        "snapshot_at": snap.snapshot_at.isoformat(),
    }


# ------------------------------------------------------------------ #
# Risk settings (read-only via API)
# ------------------------------------------------------------------ #

@router.get("/risk/settings")
async def get_risk_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    from jarvis.execution.models import RiskSettings

    result = await session.execute(select(RiskSettings).limit(1))
    settings = result.scalar_one_or_none()
    if not settings:
        return {"message": "No risk settings configured yet — using defaults"}
    return {
        "daily_loss_limit_pct": settings.daily_loss_limit_pct,
        "max_exposure_per_symbol_pct": settings.max_exposure_per_symbol_pct,
        "max_position_size_pct": settings.max_position_size_pct,
        "min_risk_reward": settings.min_risk_reward,
        "max_data_age_seconds": settings.max_data_age_seconds,
        "kill_switch": settings.kill_switch,
    }
