"""Risk Engine — deterministic, cannot be overridden by LLM or any agent.

Every check is a pure function. No async, no DB calls inside checks.
Fail closed: any unexpected exception → FAIL.

Checks (all must pass for PASS verdict):
1. kill_switch — global halt flag
2. stale_data — market data must be fresh
3. daily_loss_limit — portfolio daily loss within limit
4. symbol_exposure — existing exposure for the symbol within limit
5. position_size — proposed position size within limit
6. risk_reward — R:R ratio meets minimum
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from jarvis.agents.contracts import RiskCheckResult, RiskVerdict, TradeProposal

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RiskContext:
    """Snapshot of portfolio/system state at the moment of risk check.
    All values are pre-fetched by the caller — the engine is stateless.
    """
    kill_switch_active: bool
    data_age_seconds: float          # seconds since last market data
    max_data_age_seconds: int        # from risk_settings
    daily_pnl_pct: float             # today's P&L as % of starting balance (negative = loss)
    daily_loss_limit_pct: float      # from risk_settings (positive value, e.g. 2.0 = 2%)
    symbol_exposure_pct: float       # current exposure for this symbol as % of balance
    max_exposure_per_symbol_pct: float
    max_position_size_pct: float
    min_risk_reward: float


def evaluate(proposal: TradeProposal, ctx: RiskContext) -> RiskCheckResult:
    """
    Deterministic risk evaluation. Returns PASS or FAIL with reasons.
    Never raises — any internal error becomes a FAIL.
    """
    passed: list[str] = []
    failed: list[str] = []

    try:
        # 1. Kill switch
        if ctx.kill_switch_active:
            failed.append("kill_switch")
            logger.warning("risk.kill_switch_active", symbol=proposal.symbol)
        else:
            passed.append("kill_switch")

        # 2. Stale data
        if ctx.data_age_seconds > ctx.max_data_age_seconds:
            failed.append("stale_data")
            logger.warning(
                "risk.stale_data",
                age=ctx.data_age_seconds,
                max=ctx.max_data_age_seconds,
            )
        else:
            passed.append("stale_data")

        # 3. Daily loss limit (daily_pnl_pct is negative when losing)
        if ctx.daily_pnl_pct <= -ctx.daily_loss_limit_pct:
            failed.append("daily_loss_limit")
            logger.warning("risk.daily_loss_limit_hit", daily_pnl=ctx.daily_pnl_pct)
        else:
            passed.append("daily_loss_limit")

        # 4. Symbol exposure
        if ctx.symbol_exposure_pct + proposal.position_size_pct > ctx.max_exposure_per_symbol_pct:
            failed.append("symbol_exposure")
            logger.warning(
                "risk.symbol_exposure_exceeded",
                current=ctx.symbol_exposure_pct,
                proposed=proposal.position_size_pct,
                limit=ctx.max_exposure_per_symbol_pct,
            )
        else:
            passed.append("symbol_exposure")

        # 5. Position size
        if proposal.position_size_pct > ctx.max_position_size_pct:
            failed.append("position_size")
            logger.warning("risk.position_size_exceeded", size=proposal.position_size_pct)
        else:
            passed.append("position_size")

        # 6. Risk/reward
        if proposal.risk_reward_ratio < ctx.min_risk_reward:
            failed.append("risk_reward")
            logger.warning(
                "risk.rr_below_minimum",
                rr=proposal.risk_reward_ratio,
                min=ctx.min_risk_reward,
            )
        else:
            passed.append("risk_reward")

    except Exception as exc:  # noqa: BLE001 — fail closed on any unexpected error
        logger.error("risk.unexpected_error", error_type=type(exc).__name__)
        failed.append("unexpected_error")

    verdict = RiskVerdict.PASS if not failed else RiskVerdict.FAIL
    reason = f"Failed checks: {', '.join(failed)}" if failed else None

    logger.info(
        "risk.verdict",
        verdict=verdict,
        symbol=proposal.symbol,
        passed=passed,
        failed=failed,
    )

    return RiskCheckResult(
        verdict=verdict,
        checks_passed=passed,
        checks_failed=failed,
        reason=reason,
        checked_at=datetime.now(UTC),
    )
