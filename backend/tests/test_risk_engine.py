"""Tests — Risk Engine: all check paths, fail closed behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest

from jarvis.agents.contracts import RiskVerdict, SignalDirection, TradeProposal
from jarvis.risk.engine import RiskContext, evaluate


def _make_proposal(**overrides) -> TradeProposal:
    defaults = dict(
        proposal_id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        symbol="BTCUSDT",
        market="spot",
        direction=SignalDirection.LONG,
        entry_price=30000.0,
        stop_loss=29000.0,
        take_profit=32000.0,
        risk_reward_ratio=2.0,
        position_size_pct=5.0,
        confidence=0.75,
        evidence_summary="Test evidence for risk engine evaluation",
        market_report_id=uuid.uuid4(),
        news_report_id=uuid.uuid4(),
        expiry_seconds=300,
    )
    defaults.update(overrides)
    return TradeProposal(**defaults)


def _safe_ctx(**overrides) -> RiskContext:
    defaults = dict(
        kill_switch_active=False,
        data_age_seconds=60.0,
        max_data_age_seconds=300,
        daily_pnl_pct=-0.5,
        daily_loss_limit_pct=2.0,
        symbol_exposure_pct=0.0,
        max_exposure_per_symbol_pct=10.0,
        max_position_size_pct=10.0,
        min_risk_reward=1.5,
    )
    defaults.update(overrides)
    return RiskContext(**defaults)


# ------------------------------------------------------------------ #
# PASS cases
# ------------------------------------------------------------------ #

def test_all_checks_pass_gives_pass_verdict() -> None:
    result = evaluate(_make_proposal(), _safe_ctx())
    assert result.verdict == RiskVerdict.PASS
    assert not result.checks_failed
    assert len(result.checks_passed) == 6


def test_pass_result_has_timestamp() -> None:
    result = evaluate(_make_proposal(), _safe_ctx())
    assert result.checked_at <= datetime.now(UTC)


# ------------------------------------------------------------------ #
# Kill switch
# ------------------------------------------------------------------ #

def test_kill_switch_fails() -> None:
    result = evaluate(_make_proposal(), _safe_ctx(kill_switch_active=True))
    assert result.verdict == RiskVerdict.FAIL
    assert "kill_switch" in result.checks_failed
    assert result.reason is not None


def test_kill_switch_off_passes() -> None:
    result = evaluate(_make_proposal(), _safe_ctx(kill_switch_active=False))
    assert "kill_switch" in result.checks_passed


# ------------------------------------------------------------------ #
# Stale data
# ------------------------------------------------------------------ #

def test_stale_data_fails() -> None:
    result = evaluate(_make_proposal(), _safe_ctx(data_age_seconds=600, max_data_age_seconds=300))
    assert "stale_data" in result.checks_failed
    assert result.verdict == RiskVerdict.FAIL


def test_fresh_data_passes() -> None:
    result = evaluate(_make_proposal(), _safe_ctx(data_age_seconds=10, max_data_age_seconds=300))
    assert "stale_data" in result.checks_passed


def test_exactly_at_limit_passes() -> None:
    result = evaluate(_make_proposal(), _safe_ctx(data_age_seconds=300, max_data_age_seconds=300))
    assert "stale_data" in result.checks_passed


# ------------------------------------------------------------------ #
# Daily loss limit
# ------------------------------------------------------------------ #

def test_daily_loss_limit_hit_fails() -> None:
    result = evaluate(_make_proposal(), _safe_ctx(daily_pnl_pct=-2.0, daily_loss_limit_pct=2.0))
    assert "daily_loss_limit" in result.checks_failed


def test_daily_loss_just_below_limit_passes() -> None:
    result = evaluate(_make_proposal(), _safe_ctx(daily_pnl_pct=-1.99, daily_loss_limit_pct=2.0))
    assert "daily_loss_limit" in result.checks_passed


def test_positive_daily_pnl_passes() -> None:
    result = evaluate(_make_proposal(), _safe_ctx(daily_pnl_pct=1.5))
    assert "daily_loss_limit" in result.checks_passed


# ------------------------------------------------------------------ #
# Symbol exposure
# ------------------------------------------------------------------ #

def test_symbol_exposure_exceeded_fails() -> None:
    proposal = _make_proposal(position_size_pct=8.0)
    result = evaluate(proposal, _safe_ctx(symbol_exposure_pct=5.0, max_exposure_per_symbol_pct=10.0))
    assert "symbol_exposure" in result.checks_failed


def test_symbol_exposure_within_limit_passes() -> None:
    proposal = _make_proposal(position_size_pct=3.0)
    result = evaluate(proposal, _safe_ctx(symbol_exposure_pct=5.0, max_exposure_per_symbol_pct=10.0))
    assert "symbol_exposure" in result.checks_passed


# ------------------------------------------------------------------ #
# Position size
# ------------------------------------------------------------------ #

def test_position_size_exceeds_max_fails() -> None:
    proposal = _make_proposal(position_size_pct=15.0)
    result = evaluate(proposal, _safe_ctx(max_position_size_pct=10.0))
    assert "position_size" in result.checks_failed


def test_position_size_at_limit_passes() -> None:
    proposal = _make_proposal(position_size_pct=10.0)
    result = evaluate(proposal, _safe_ctx(max_position_size_pct=10.0))
    assert "position_size" in result.checks_passed


# ------------------------------------------------------------------ #
# Risk/reward
# ------------------------------------------------------------------ #

def test_rr_below_minimum_fails() -> None:
    proposal = _make_proposal(risk_reward_ratio=1.0)
    result = evaluate(proposal, _safe_ctx(min_risk_reward=1.5))
    assert "risk_reward" in result.checks_failed


def test_rr_at_minimum_passes() -> None:
    proposal = _make_proposal(risk_reward_ratio=1.5)
    result = evaluate(proposal, _safe_ctx(min_risk_reward=1.5))
    assert "risk_reward" in result.checks_passed


# ------------------------------------------------------------------ #
# Multiple simultaneous failures
# ------------------------------------------------------------------ #

def test_multiple_failures_all_reported() -> None:
    proposal = _make_proposal(position_size_pct=50.0, risk_reward_ratio=0.5)
    ctx = _safe_ctx(
        kill_switch_active=True,
        data_age_seconds=9999,
        daily_pnl_pct=-5.0,
    )
    result = evaluate(proposal, ctx)
    assert result.verdict == RiskVerdict.FAIL
    # At least kill_switch, stale_data, daily_loss_limit, position_size, risk_reward should fail
    assert len(result.checks_failed) >= 4


# ------------------------------------------------------------------ #
# Fail closed on bad input
# ------------------------------------------------------------------ #

def test_zero_rr_ratio_rejected_by_contract() -> None:
    """risk_reward_ratio=0 is rejected at the Pydantic contract level (gt=0 constraint)."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        _make_proposal(risk_reward_ratio=0.0)


# ------------------------------------------------------------------ #
# Contracts
# ------------------------------------------------------------------ #

def test_risk_check_result_is_immutable() -> None:
    result = evaluate(_make_proposal(), _safe_ctx())
    with pytest.raises(Exception):
        result.verdict = RiskVerdict.FAIL  # type: ignore[misc]
