"""ORM models — news domain."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.base import Base


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # rss | api
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    credibility_base: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    documents: Mapped[list[NewsDocument]] = relationship(back_populates="source", cascade="all, delete-orphan")


class NewsDocument(Base):
    __tablename__ = "news_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_sources.id", ondelete="CASCADE"))
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # sha256 of URL
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(16))
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    event_type: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str | None] = mapped_column(Text)
    credibility_score: Mapped[float | None] = mapped_column(Float)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[NewsSource] = relationship(back_populates="documents")
    mentions: Mapped[list[NewsMention]] = relationship(back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_news_documents_published_at", "published_at"),
    )


class NewsEvent(Base):
    __tablename__ = "news_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(String(16))
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    corroboration_count: Mapped[int] = mapped_column(default=1, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mentions: Mapped[list[NewsMention]] = relationship(back_populates="event")

    __table_args__ = (
        Index("ix_news_events_type_seen", "event_type", "first_seen_at"),
    )


class NewsMention(Base):
    __tablename__ = "news_mentions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_documents.id", ondelete="CASCADE"))
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("news_events.id", ondelete="SET NULL"))
    symbol: Mapped[str | None] = mapped_column(String(32))
    mention_context: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[NewsDocument] = relationship(back_populates="mentions")
    event: Mapped[NewsEvent | None] = relationship(back_populates="mentions")

    __table_args__ = (
        UniqueConstraint("document_id", "symbol", name="uq_news_mentions_doc_symbol"),
        Index("ix_news_mentions_symbol", "symbol"),
    )
