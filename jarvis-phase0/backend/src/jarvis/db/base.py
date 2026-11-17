"""Async database + Redis plumbing: engine, session factory, FastAPI dependency, health probes."""

import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache

import structlog
from redis.asyncio import Redis
from sqlalchemy import MetaData, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from jarvis.config.settings import get_settings
from jarvis.core.errors import DatabaseError

logger = structlog.get_logger(__name__)

PROBE_TIMEOUT_SECONDS = 3.0

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for every ORM model (Alembic autogenerate targets ``Base.metadata``)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# --------------------------------------------------------------------------- #
# Engine / sessions
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Create the process-wide async engine (lazy: no connection is opened here)."""
    settings = get_settings()
    connect_args: dict[str, object] = {"timeout": 10, "command_timeout": 30}
    if settings.database_ssl:
        connect_args["ssl"] = "require"
    return create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=1800,
        pool_pre_ping=True,  # session poolers drop idle connections
        connect_args=connect_args,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request; commit on success, rollback on any failure."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("db.session_failed", error_type=type(exc).__name__)
            raise DatabaseError from exc
        except BaseException:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close pooled connections (call on shutdown). Safe if the engine was never created."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
        get_session_factory.cache_clear()


# --------------------------------------------------------------------------- #
# Redis
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def get_redis() -> Redis:
    """Create the process-wide async Redis client (lazy: connects on first command)."""
    return Redis.from_url(
        get_settings().redis_url.get_secret_value(),
        socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
        socket_timeout=PROBE_TIMEOUT_SECONDS,
        health_check_interval=30,
        decode_responses=True,
    )


async def close_redis() -> None:
    if get_redis.cache_info().currsize:
        await get_redis().aclose()
        get_redis.cache_clear()


# --------------------------------------------------------------------------- #
# Probes (used by /ready). They never raise: any failure means "not ready".
# --------------------------------------------------------------------------- #
async def check_database(engine: AsyncEngine | None = None) -> bool:
    try:
        target = engine or get_engine()
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            async with target.connect() as connection:
                await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - fail closed on *any* error
        logger.warning("ready.database_failed", error_type=type(exc).__name__)
        return False


async def check_redis(client: Redis | None = None) -> bool:
    try:
        target = client or get_redis()
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            return bool(await target.ping())
    except Exception as exc:  # noqa: BLE001 - fail closed on *any* error
        logger.warning("ready.redis_failed", error_type=type(exc).__name__)
        return False
