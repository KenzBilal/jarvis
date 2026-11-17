"""Market Analyst agent.

Reads candles + indicators from DB, asks the LLM for a structured analysis,
validates the response as a MarketReport, persists the run + report.

If AI_PROVIDER is not set, the agent returns a stub report (Phase 1 compat).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.contracts import (
    MarketReport,
    MarketStructure,
    RunStatus,
    Sentiment,
    SignalDirection,
    TechnicalIndicators,
)
from jarvis.agents.llm import ConfigurationError, complete_json
from jarvis.core.logging import correlation_context

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are JARVIS Market Analyst — an expert quantitative crypto analyst.
Analyze the provided technical data and return ONLY valid JSON matching this schema:
{
  "signal": "long" | "short" | "no_trade",
  "confidence": 0.0-1.0,
  "trend": "uptrend" | "downtrend" | "sideways",
  "support_levels": [<price>, ...],
  "resistance_levels": [<price>, ...],
  "key_observations": ["...", ...],
  "reasoning": "<detailed reasoning min 50 chars>"
}
Rules:
- NO_TRADE is always a valid signal — never force a trade.
- confidence < 0.6 → signal should usually be no_trade.
- reasoning must cite specific indicator values.
- Return ONLY the JSON object, no markdown, no explanation outside it.
"""


async def run_market_analysis(
    symbol: str,
    market: str,
    timeframe: str,
    indicators: dict,
    candles_summary: str,
    session: AsyncSession,
    *,
    correlation_id: str | None = None,
) -> MarketReport:
    """Run market analysis for one symbol. Returns MarketReport."""
    run_id = uuid.uuid4()

    with correlation_context(correlation_id):
        logger.info("market_analyst.start", symbol=symbol, market=market, run_id=str(run_id))

        user_prompt = f"""Symbol: {symbol} ({market.upper()}) | Timeframe: {timeframe}

Technical Indicators (latest values):
{_format_indicators(indicators)}

Recent price action summary:
{candles_summary}

Provide your structured analysis as JSON."""

        try:
            raw = await complete_json(_SYSTEM_PROMPT, user_prompt)
            report = _parse_llm_output(raw, run_id=run_id, symbol=symbol, market=market,
                                        timeframe=timeframe, indicators=indicators)
        except ConfigurationError:
            logger.warning("market_analyst.no_llm_provider", symbol=symbol)
            report = _stub_report(run_id, symbol, market, timeframe, indicators)

        logger.info(
            "market_analyst.done",
            symbol=symbol,
            signal=report.signal,
            confidence=report.confidence,
            run_id=str(run_id),
        )
        await _persist_report(report, session)
        return report


def _format_indicators(ind: dict) -> str:
    lines = []
    for k, v in ind.items():
        lines.append(f"  {k}: {round(v, 4) if v is not None else 'N/A'}")
    return "\n".join(lines)


def _parse_llm_output(
    raw: dict,
    *,
    run_id: uuid.UUID,
    symbol: str,
    market: str,
    timeframe: str,
    indicators: dict,
) -> MarketReport:
    return MarketReport(
        run_id=run_id,
        symbol=symbol,
        market=market,
        timeframe=timeframe,
        generated_at=datetime.now(UTC),
        signal=SignalDirection(raw.get("signal", "no_trade")),
        confidence=float(raw.get("confidence", 0.0)),
        indicators=TechnicalIndicators(**{k: v for k, v in indicators.items() if k in TechnicalIndicators.model_fields}),
        structure=MarketStructure(
            trend=raw.get("trend", "sideways"),
            support_levels=[float(p) for p in raw.get("support_levels", [])],
            resistance_levels=[float(p) for p in raw.get("resistance_levels", [])],
            key_observations=raw.get("key_observations", []),
        ),
        reasoning=raw.get("reasoning", "No reasoning provided."),
        data_age_seconds=0.0,
    )


def _stub_report(
    run_id: uuid.UUID,
    symbol: str,
    market: str,
    timeframe: str,
    indicators: dict,
) -> MarketReport:
    """Returned when AI_PROVIDER is not configured — always NO_TRADE."""
    return MarketReport(
        run_id=run_id,
        symbol=symbol,
        market=market,
        timeframe=timeframe,
        generated_at=datetime.now(UTC),
        signal=SignalDirection.NO_TRADE,
        confidence=0.0,
        indicators=TechnicalIndicators(**{k: v for k, v in indicators.items() if k in TechnicalIndicators.model_fields}),
        structure=MarketStructure(
            trend="sideways",
            support_levels=[],
            resistance_levels=[],
            key_observations=["AI provider not configured — stub report"],
        ),
        reasoning="AI_PROVIDER env var not set. Configure it to enable real analysis.",
        data_age_seconds=0.0,
    )


async def _persist_report(report: MarketReport, session: AsyncSession) -> None:
    from jarvis.agents.models import AgentReport, AgentRun

    run = AgentRun(
        id=report.run_id,
        agent_type="market_analyst",
        status=RunStatus.SUCCESS,
        started_at=report.generated_at,
        finished_at=datetime.now(UTC),
    )
    session.add(run)

    agent_report = AgentReport(
        run_id=report.run_id,
        agent_type="market_analyst",
        report_type="market_analysis",
        payload=report.model_dump(mode="json"),
    )
    session.add(agent_report)
    await session.flush()
