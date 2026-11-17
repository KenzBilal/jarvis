"""Tests — agents: contracts validation, news collector, LLM stub paths."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest

from jarvis.agents.contracts import (
    MarketReport,
    MarketStructure,
    NewsArticle,
    NewsEventType,
    NewsReport,
    RiskCheckResult,
    RiskVerdict,
    Sentiment,
    SignalDirection,
    TechnicalIndicators,
    TradeProposal,
)
from jarvis.news.collector import (
    RawArticle,
    compute_credibility,
    url_hash,
)


# ------------------------------------------------------------------ #
# Contracts
# ------------------------------------------------------------------ #

def _market_report(**overrides) -> MarketReport:
    defaults = dict(
        run_id=uuid.uuid4(),
        symbol="BTCUSDT",
        market="spot",
        timeframe="1h",
        generated_at=datetime.now(UTC),
        signal=SignalDirection.LONG,
        confidence=0.75,
        indicators=TechnicalIndicators(rsi_14=55.0, ema_20=30100.0),
        structure=MarketStructure(trend="uptrend", key_observations=["RSI trending up"]),
        reasoning="RSI at 55 and rising, EMA cross confirmed uptrend.",
        data_age_seconds=30.0,
    )
    defaults.update(overrides)
    return MarketReport(**defaults)


def test_market_report_valid() -> None:
    r = _market_report()
    assert r.signal == SignalDirection.LONG
    assert r.confidence == 0.75


def test_market_report_confidence_bounded() -> None:
    with pytest.raises(Exception):
        _market_report(confidence=1.5)
    with pytest.raises(Exception):
        _market_report(confidence=-0.1)


def test_market_report_reasoning_min_length() -> None:
    with pytest.raises(Exception):
        _market_report(reasoning="short")


def test_market_report_is_frozen() -> None:
    r = _market_report()
    with pytest.raises(Exception):
        r.signal = SignalDirection.NO_TRADE  # type: ignore[misc]


def test_trade_proposal_valid() -> None:
    p = TradeProposal(
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
        confidence=0.8,
        evidence_summary="Market and news aligned. RSI breakout confirmed with volume.",
        market_report_id=uuid.uuid4(),
        news_report_id=uuid.uuid4(),
    )
    assert p.direction == SignalDirection.LONG


def test_trade_proposal_entry_must_be_positive() -> None:
    with pytest.raises(Exception):
        TradeProposal(
            proposal_id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            symbol="BTCUSDT",
            market="spot",
            direction=SignalDirection.LONG,
            entry_price=-1.0,
            stop_loss=29000.0,
            take_profit=32000.0,
            risk_reward_ratio=2.0,
            position_size_pct=5.0,
            confidence=0.8,
            evidence_summary="x" * 20,
            market_report_id=uuid.uuid4(),
            news_report_id=uuid.uuid4(),
        )


def test_news_report_valid() -> None:
    r = NewsReport(
        run_id=uuid.uuid4(),
        generated_at=datetime.now(UTC),
        symbols_mentioned=["BTC", "ETH"],
        overall_sentiment=Sentiment.BULLISH,
        sentiment_score=0.6,
        top_articles=[],
        key_events=["Bitcoin ETF approved"],
        reasoning="Multiple credible sources report positive regulatory news.",
    )
    assert r.overall_sentiment == Sentiment.BULLISH


# ------------------------------------------------------------------ #
# News collector utilities
# ------------------------------------------------------------------ #

def test_url_hash_is_sha256_hex() -> None:
    url = "https://coindesk.com/article/123"
    h = url_hash(url)
    assert h == hashlib.sha256(url.encode()).hexdigest()
    assert len(h) == 64


def test_url_hash_different_urls_differ() -> None:
    assert url_hash("https://a.com") != url_hash("https://b.com")


def _raw_article(url: str = "https://example.com", title: str = "BTC hits ATH") -> RawArticle:
    return RawArticle(url=url, title=title, source="TestSource", published_at=datetime.now(UTC))


def test_credibility_boosts_for_corroborated_topics() -> None:
    art1 = _raw_article(title="Bitcoin ETF approved by SEC today")
    art2 = _raw_article(url="https://other.com", title="Bitcoin ETF gets SEC approval")
    art3 = _raw_article(url="https://third.com", title="Bitcoin ETF approved by regulators")

    score_alone = compute_credibility(art1, [art1])
    score_corroborated = compute_credibility(art1, [art1, art2, art3])
    assert score_corroborated > score_alone


def test_credibility_capped_at_1() -> None:
    art = _raw_article(title="Bitcoin price crash")
    others = [_raw_article(url=f"https://s{i}.com", title="Bitcoin price crash imminent") for i in range(20)]
    score = compute_credibility(art, [art] + others)
    assert score <= 1.0


def test_credibility_no_boost_for_unrelated() -> None:
    art = _raw_article(title="Bitcoin price crash")
    unrelated = _raw_article(url="https://other.com", title="Ethereum staking rewards increase")
    score = compute_credibility(art, [art, unrelated])
    assert score == pytest.approx(0.5)  # base score only


# ------------------------------------------------------------------ #
# Agent stub behaviour (no LLM configured)
# ------------------------------------------------------------------ #

def test_market_analyst_stub_returns_no_trade(monkeypatch) -> None:
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from jarvis.agents import market_analyst

    monkeypatch.setattr(market_analyst, "complete_json", AsyncMock(side_effect=Exception("no provider")))

    # Test that _stub_report produces NO_TRADE
    report = market_analyst._stub_report(
        uuid.uuid4(), "BTCUSDT", "spot", "1h",
        {"rsi_14": 55.0, "ema_20": 30000.0}
    )
    assert report.signal == SignalDirection.NO_TRADE
    assert report.confidence == 0.0


def test_chief_analyst_low_rr_returns_none() -> None:
    from jarvis.agents.chief_analyst import _parse_decision

    market = _market_report()
    news = NewsReport(
        run_id=uuid.uuid4(),
        generated_at=datetime.now(UTC),
        symbols_mentioned=["BTC"],
        overall_sentiment=Sentiment.BULLISH,
        sentiment_score=0.5,
        top_articles=[],
        key_events=[],
        reasoning="Some valid reasoning text here.",
    )

    # R:R = (32000-30000)/(30000-29500) = 2000/500 = 4.0 — passes
    result = _parse_decision(
        {"decision": "trade", "direction": "long",
         "entry_price": 30000, "stop_loss": 29500, "take_profit": 32000,
         "confidence": 0.8, "position_size_pct": 5,
         "evidence_summary": "Strong setup with volume confirmation and RSI breakout"},
        uuid.uuid4(), market, news
    )
    assert result is not None
    assert result.risk_reward_ratio == pytest.approx(4.0)


def test_chief_analyst_rr_below_15_returns_none() -> None:
    from jarvis.agents.chief_analyst import _parse_decision

    market = _market_report()
    news = NewsReport(
        run_id=uuid.uuid4(),
        generated_at=datetime.now(UTC),
        symbols_mentioned=["BTC"],
        overall_sentiment=Sentiment.BULLISH,
        sentiment_score=0.5,
        top_articles=[],
        key_events=[],
        reasoning="Some valid reasoning text here.",
    )

    # R:R = (30500-30000)/(30000-29900) = 500/100 = 5.0 — wait this passes
    # Let's make it fail: (30100-30000)/(30000-29900) = 100/100 = 1.0 < 1.5
    result = _parse_decision(
        {"decision": "trade", "direction": "long",
         "entry_price": 30000, "stop_loss": 29900, "take_profit": 30100,
         "confidence": 0.8, "position_size_pct": 5,
         "evidence_summary": "Weak setup but let's try"},
        uuid.uuid4(), market, news
    )
    assert result is None  # R:R = 1.0, below 1.5 minimum
