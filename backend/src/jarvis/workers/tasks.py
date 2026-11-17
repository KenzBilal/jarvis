"""arq worker. Run with: ``uv run arq jarvis.workers.tasks.WorkerSettings``."""

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from arq import cron
from arq.connections import RedisSettings

from jarvis.config.settings import get_settings
from jarvis.core.errors import retry_async
from jarvis.core.logging import configure_logging, correlation_context

logger = structlog.get_logger(__name__)

HEARTBEAT_KEY = "jarvis:worker:heartbeat"
HEARTBEAT_TTL_SECONDS = 120


async def heartbeat(ctx: dict[str, Any]) -> str:
    """Record that the worker is alive: set a TTL'd Redis key and log a structured event.

    The key expires on its own, so a dead worker is visible as a missing key.
    """
    with correlation_context():
        redis = ctx["redis"]
        stamp = datetime.now(UTC).isoformat()
        await retry_async(
            lambda: redis.set(HEARTBEAT_KEY, stamp, ex=HEARTBEAT_TTL_SECONDS),
            attempts=3,
            base_delay=0.2,
            operation="worker.heartbeat.write",
        )
        logger.info(
            "worker.heartbeat",
            timestamp=stamp,
            job_try=ctx.get("job_try"),
            uptime_seconds=round(time.monotonic() - ctx.get("started_monotonic", time.monotonic()), 1),
        )
        return stamp


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    if settings.trading_mode != "paper" or settings.live_trading_enabled:
        raise RuntimeError("refusing to start: live trading is not available in this phase")
    configure_logging(settings.log_level, environment=settings.jarvis_env)
    ctx["started_monotonic"] = time.monotonic()
    logger.info("worker.startup", env=settings.jarvis_env, trading_mode=settings.trading_mode)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker.shutdown")


class WorkerSettings:
    """arq configuration. ``on_startup`` fails closed if settings are invalid."""

    functions = [heartbeat]
    cron_jobs = [cron(heartbeat, second={0, 30}, run_at_startup=True, unique=True, max_tries=1)]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url.get_secret_value())
    max_jobs = 10
    job_timeout = 30
    max_tries = 3
    keep_result = 60
    health_check_interval = 30
    retry_jobs = True
    allow_abort_jobs = False
