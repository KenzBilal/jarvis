"""Agent Pydantic contracts — shared across all phases.

All inter-agent communication uses these validated schemas.
No LLM output is accepted without passing through one of these models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------------ #
# Enums
# ------------------------------------------------------------------ #

class AgentType(str, Enum):
    MARKET_ANALYST = "market_analyst"
    NEWS_INTELLIGENCE = "news_intelligence"
    CHIEF_ANALYST = "chief_analyst"
    RISK_ENGINE = "risk_engine"
    EXECUTION_ENGINE = "execution_engine"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NO_TRADE = "no_trade"


class Sentiment(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ------------------------------------------------------------------ #
# Market Analysis
# ------------------------------------------------------------------ #

class TechnicalIndicators(BaseModel):
    rsi_14: float | None = None
    ema_20: float | None = None
    ema_50: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    atr_14: float | None = None


class MarketStructure(BaseModel):
    trend: str  # "uptrend" | "downtrend" | "sideways"
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)
    key_observations: list[str] = Field(default_factory=list)


class MarketReport(BaseModel):
    """Output of the Market Analyst agent."""
    run_id: uuid.UUID
    symbol: str
    market: str  # spot | futures
    timeframe: str
    generated_at: datetime
    signal: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    indicators: TechnicalIndicators
    structure: MarketStructure
    reasoning: str = Field(min_length=10)
    data_age_seconds: float  # how old the most recent candle is

    @field_validator("data_age_seconds")
    @classmethod
    def _not_stale(cls, v: float) -> float:
        # Warn only — engine will hard-reject stale data
        return v

    model_config = {"frozen": True}


# ------------------------------------------------------------------ #
# News Intelligence
# ------------------------------------------------------------------ #

class NewsEventType(str, Enum):
    REGULATORY = "regulatory"
    TECHNICAL = "technical"
    MACRO = "macro"
    EXCHANGE = "exchange"
    PARTNERSHIP = "partnership"
    HACK_EXPLOIT = "hack_exploit"
    OTHER = "other"


class NewsArticle(BaseModel):
    url: str
    title: str
    source: str
    published_at: datetime
    sentiment: Sentiment
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    event_type: NewsEventType
    credibility_score: float = Field(ge=0.0, le=1.0)
    summary: str


class NewsReport(BaseModel):
    """Output of the News Intelligence agent."""
    run_id: uuid.UUID
    generated_at: datetime
    symbols_mentioned: list[str]
    overall_sentiment: Sentiment
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    top_articles: list[NewsArticle]
    key_events: list[str]
    reasoning: str = Field(min_length=10)

    model_config = {"frozen": True}


# ------------------------------------------------------------------ #
# Trade Proposals
# ------------------------------------------------------------------ #

class TradeProposal(BaseModel):
    """Structured trade proposal from Chief Analyst."""
    proposal_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime
    symbol: str
    market: str  # spot | futures
    direction: SignalDirection  # never NO_TRADE here — that returns None
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    risk_reward_ratio: float = Field(gt=0)
    position_size_pct: float = Field(gt=0, le=100)  # % of available balance
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_summary: str = Field(min_length=20)
    market_report_id: uuid.UUID
    news_report_id: uuid.UUID
    expiry_seconds: int = 300  # proposal expires if not approved within N seconds

    @field_validator("risk_reward_ratio", mode="before")
    @classmethod
    def _compute_rr(cls, v: Any) -> Any:
        return v  # caller pre-computes; validator just passes through

    model_config = {"frozen": True}


# ------------------------------------------------------------------ #
# Risk Check
# ------------------------------------------------------------------ #

class RiskVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class RiskCheckResult(BaseModel):
    verdict: RiskVerdict
    checks_passed: list[str]
    checks_failed: list[str]
    reason: str | None = None  # filled when FAIL
    checked_at: datetime

    model_config = {"frozen": True}


# ------------------------------------------------------------------ #
# Approval
# ------------------------------------------------------------------ #

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ProposalApproval(BaseModel):
    proposal_id: uuid.UUID
    telegram_user_id: int
    status: ApprovalStatus
    decided_at: datetime | None = None
    comment: str | None = None

    model_config = {"frozen": True}
