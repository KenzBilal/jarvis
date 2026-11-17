"""SQLAlchemy ORM models — market domain.

All tables follow the global conventions in ``db.base``:
  * UUID PKs
  * ``timestamptz`` via ``DateTime(timezone=True)``
  * ``created_at`` / ``updated_at`` everywhere
  * Composite unique constraints on natural keys
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.base import Base


class TradingSymbol(Base):
    __tablename__ = "trading_symbols"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)  # spot | futures
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    volume_24h_usdt: Mapped[float | None] = mapped_column(Float)
    price_change_pct_24h: Mapped[float | None] = mapped_column(Float)
    last_price: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    filters: Mapped[list[SymbolFilter]] = relationship(back_populates="symbol_ref", cascade="all, delete-orphan")
    candles: Mapped[list[Candle]] = relationship(back_populates="symbol_ref", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("symbol", "market", name="uq_trading_symbols_symbol_market"),
    )


class SymbolFilter(Base):
    __tablename__ = "symbol_filters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trading_symbols.id", ondelete="CASCADE"))
    filter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    symbol_ref: Mapped[TradingSymbol] = relationship(back_populates="filters")

    __table_args__ = (
        UniqueConstraint("symbol_id", "filter_type", name="uq_symbol_filters_symbol_type"),
    )


class Candle(Base):
    __tablename__ = "candles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trading_symbols.id", ondelete="CASCADE"))
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)  # 1m, 5m, 1h, 4h, 1d
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    quote_volume: Mapped[float] = mapped_column(Float, nullable=False)
    num_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    symbol_ref: Mapped[TradingSymbol] = relationship(back_populates="candles")

    __table_args__ = (
        UniqueConstraint("symbol_id", "timeframe", "open_time", name="uq_candles_symbol_tf_time"),
        Index("ix_candles_symbol_tf_time", "symbol_id", "timeframe", "open_time"),
    )


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trading_symbols.id", ondelete="CASCADE"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    best_bid: Mapped[float | None] = mapped_column(Float)
    best_ask: Mapped[float | None] = mapped_column(Float)
    last_price: Mapped[float | None] = mapped_column(Float)
    volume_24h: Mapped[float | None] = mapped_column(Float)
    price_change_pct: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_market_snapshots_symbol_time", "symbol_id", "captured_at"),
    )


class IndicatorSnapshot(Base):
    __tablename__ = "indicators"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trading_symbols.id", ondelete="CASCADE"))
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rsi_14: Mapped[float | None] = mapped_column(Float)
    ema_20: Mapped[float | None] = mapped_column(Float)
    ema_50: Mapped[float | None] = mapped_column(Float)
    macd_line: Mapped[float | None] = mapped_column(Float)
    macd_signal: Mapped[float | None] = mapped_column(Float)
    macd_hist: Mapped[float | None] = mapped_column(Float)
    bb_upper: Mapped[float | None] = mapped_column(Float)
    bb_middle: Mapped[float | None] = mapped_column(Float)
    bb_lower: Mapped[float | None] = mapped_column(Float)
    atr_14: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol_id", "timeframe", "computed_at", name="uq_indicators_symbol_tf_time"),
        Index("ix_indicators_symbol_tf_time", "symbol_id", "timeframe", "computed_at"),
    )
