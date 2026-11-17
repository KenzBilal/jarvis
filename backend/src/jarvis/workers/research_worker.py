"""arq worker tasks for scanner, research, and monitoring cycles."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from arq import cron
from arq.connections import RedisSettings

from jarvis.config.settings import get_settings
from jarvis.core.logging import configure_logging, correlation_context
from jarvis.workers.tasks import HEARTBEAT_KEY, HEARTBEAT_TTL_SECONDS

logger = structlog.get_logger(__name__)


# ------------------------------------------------------------------ #
# Scanner job
# ------------------------------------------------------------------ #

async def run_scanner(ctx: dict[str, Any]) -> dict:
    """Discover eligible symbols and store to DB."""
    with correlation_context() as cid:
        logger.info("scanner_job.start")
        try:
            from jarvis.market.binance_client import BinanceClient
            from jarvis.market.scanner import MarketScanner
            from jarvis.db.base import get_session_factory

            async with BinanceClient() as client:
                scanner = MarketScanner(client)
                spot = await scanner.scan_spot()
                futures = await scanner.scan_futures()

            logger.info(
                "scanner_job.done",
                spot_count=len(spot),
                futures_count=len(futures),
                correlation_id=cid,
            )
            return {"spot": len(spot), "futures": len(futures), "correlation_id": cid}
        except Exception as exc:
            logger.error("scanner_job.failed", error_type=type(exc).__name__)
            return {"error": type(exc).__name__, "correlation_id": cid}


# ------------------------------------------------------------------ #
# Research job
# ------------------------------------------------------------------ #

async def run_research(ctx: dict[str, Any], symbol: str = "BTCUSDT") -> dict:
    """Run full research cycle for a symbol: market + news + chief analysis."""
    with correlation_context() as cid:
        logger.info("research_job.start", symbol=symbol)
        try:
            # Phase 2+: This is where agents run. Stubbed until AI key added.
            logger.info("research_job.stubbed", symbol=symbol,
                        reason="AI provider not configured — set AI_PROVIDER in .env")
            return {"status": "stubbed", "symbol": symbol, "correlation_id": cid}
        except Exception as exc:
            logger.error("research_job.failed", error_type=type(exc).__name__, symbol=symbol)
            return {"error": type(exc).__name__, "correlation_id": cid}


# ------------------------------------------------------------------ #
# Worker settings — extended with scanner jobs
# ------------------------------------------------------------------ #

async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    if settings.trading_mode != "paper" or settings.live_trading_enabled:
        raise RuntimeError("refusing to start: live trading is not available in this phase")
    configure_logging(settings.log_level, environment=settings.jarvis_env)
    ctx["started_monotonic"] = time.monotonic()
    logger.info("research_worker.startup", env=settings.jarvis_env)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("research_worker.shutdown")


class ResearchWorkerSettings:
    functions = [run_scanner, run_research]
    cron_jobs = [
        # Scanner runs every 30 minutes
        cron(run_scanner, minute={0, 30}, run_at_startup=True, unique=True, max_tries=1),
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url.get_secret_value())
    max_jobs = 5
    job_timeout = 120
    keep_result = 300
