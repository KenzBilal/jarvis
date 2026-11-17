"""Chief Analyst agent.

Cross-checks MarketReport + NewsReport, picks the strongest candidate,
challenges its own reasoning, and either produces a TradeProposal or NO_TRADE.

NO_TRADE is ALWAYS a valid output. Never force a trade.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.contracts import (
    MarketReport,
    NewsReport,
    SignalDirection,
    TradeProposal,
)
from jarvis.agents.llm import ConfigurationError, complete_json
from jarvis.core.logging import correlation_context

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are JARVIS Chief Analyst — the final decision maker on trade proposals.
You receive a Market Analysis and a News Intelligence report for a crypto symbol.
Your job is to cross-check both, challenge weak signals, and decide.

Return ONLY valid JSON:
{
  "decision": "trade" | "no_trade",
  "direction": "long" | "short",        // only if decision=trade
  "entry_price": <number>,              // only if decision=trade
  "stop_loss": <number>,                // only if decision=trade
  "take_profit": <number>,              // only if decision=trade
  "position_size_pct": <1-10>,          // % of balance, only if decision=trade
  "confidence": 0.0-1.0,
  "evidence_summary": "<min 30 chars>",
  "reasoning": "<detailed cross-check reasoning>"
}

Rules:
- If market and news signals conflict → no_trade.
- If confidence < 0.65 → no_trade.
- stop_loss must give risk:reward >= 1.5.
- Never set position_size_pct > 10.
- Return ONLY the JSON."""


async def run_chief_analysis(
    market_report: MarketReport,
    news_report: NewsReport,
    session: AsyncSession,
    *,
    correlation_id: str | None = None,
) -> TradeProposal | None:
    """
    Returns TradeProposal if a valid trade is identified, None for NO_TRADE.
    Always persists the chief run regardless of outcome.
    """
    run_id = uuid.uuid4()

    with correlation_context(correlation_id):
        logger.info(
            "chief_analyst.start",
            symbol=market_report.symbol,
            market_signal=market_report.signal,
            news_sentiment=news_report.overall_sentiment,
            run_id=str(run_id),
        )

        user_prompt = _build_prompt(market_report, news_report)

        try:
            raw = await complete_json(_SYSTEM_PROMPT, user_prompt, temperature=0.1)
        except ConfigurationError:
            logger.warning("chief_analyst.no_llm_provider")
            await _persist_run(run_id, "no_trade", session, market_report, news_report)
            return None

        proposal = _parse_decision(raw, run_id, market_report, news_report)

        logger.info(
            "chief_analyst.done",
            decision="trade" if proposal else "no_trade",
            symbol=market_report.symbol,
            run_id=str(run_id),
        )
        await _persist_run(run_id, "trade" if proposal else "no_trade", session, market_report, news_report)
        return proposal


def _build_prompt(market: MarketReport, news: NewsReport) -> str:
    return f"""=== MARKET ANALYSIS ===
Symbol: {market.symbol} ({market.market.upper()}) | Timeframe: {market.timeframe}
Signal: {market.signal} | Confidence: {market.confidence:.0%}
Trend: {market.structure.trend}
RSI-14: {market.indicators.rsi_14}
MACD hist: {market.indicators.macd_hist}
BB position: price vs upper={market.indicators.bb_upper} / lower={market.indicators.bb_lower}
Key observations: {'; '.join(market.structure.key_observations)}
Reasoning: {market.reasoning}

=== NEWS INTELLIGENCE ===
Overall sentiment: {news.overall_sentiment} (score: {news.sentiment_score:+.2f})
Symbols mentioned: {', '.join(news.symbols_mentioned)}
Key events: {'; '.join(news.key_events)}
Reasoning: {news.reasoning}

Cross-check both reports and make your decision as JSON."""


def _parse_decision(
    raw: dict,
    run_id: uuid.UUID,
    market: MarketReport,
    news: NewsReport,
) -> TradeProposal | None:
    if raw.get("decision") != "trade":
        return None

    direction_str = raw.get("direction", "long")
    try:
        direction = SignalDirection(direction_str)
    except ValueError:
        return None

    if direction == SignalDirection.NO_TRADE:
        return None

    entry = float(raw.get("entry_price", 0))
    sl = float(raw.get("stop_loss", 0))
    tp = float(raw.get("take_profit", 0))
    confidence = float(raw.get("confidence", 0.0))
    size_pct = float(raw.get("position_size_pct", 2.0))

    if not entry or not sl or not tp:
        logger.warning("chief_analyst.invalid_prices", entry=entry, sl=sl, tp=tp)
        return None

    # Compute risk/reward
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return None
    rr = reward / risk
    if rr < 1.5:
        logger.info("chief_analyst.rr_too_low", rr=rr)
        return None

    return TradeProposal(
        proposal_id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        symbol=market.symbol,
        market=market.market,
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        risk_reward_ratio=rr,
        position_size_pct=min(size_pct, 10.0),
        confidence=confidence,
        evidence_summary=raw.get("evidence_summary", "Chief analyst approved."),
        market_report_id=market.run_id,
        news_report_id=news.run_id,
        expiry_seconds=300,
    )


async def _persist_run(
    run_id: uuid.UUID,
    decision: str,
    session: AsyncSession,
    market: MarketReport,
    news: NewsReport,
) -> None:
    from jarvis.agents.models import AgentReport, AgentRun

    now = datetime.now(UTC)
    run = AgentRun(
        id=run_id,
        agent_type="chief_analyst",
        status="success",
        started_at=now,
        finished_at=now,
    )
    session.add(run)

    report = AgentReport(
        run_id=run_id,
        agent_type="chief_analyst",
        report_type="chief_decision",
        payload={
            "decision": decision,
            "market_report_id": str(market.run_id),
            "news_report_id": str(news.run_id),
            "symbol": market.symbol,
        },
    )
    session.add(report)
    await session.flush()
