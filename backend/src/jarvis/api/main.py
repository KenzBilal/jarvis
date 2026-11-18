"""FastAPI application factory and ASGI entrypoint (``jarvis.api.main:app``)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from jarvis import __version__
from jarvis.api.routes import health, data
from jarvis.config.settings import Settings, get_settings
from jarvis.core.errors import register_exception_handlers
from jarvis.core.logging import CorrelationIdMiddleware, configure_logging
from jarvis.db.base import close_redis, dispose_engine
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log = structlog.get_logger("jarvis.lifecycle")
    settings = get_settings()
    # Defense in depth: Settings already rejects anything but "paper".
    if settings.trading_mode != "paper" or settings.live_trading_enabled:
        raise RuntimeError("refusing to start: live trading is not available in this phase")
    log.info("app.startup", env=settings.jarvis_env, trading_mode=settings.trading_mode)
    try:
        yield
    finally:
        await dispose_engine()
        await close_redis()
        log.info("app.shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Invalid configuration raises here, so the process never serves."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, environment=settings.jarvis_env)

    app = FastAPI(
        title="JARVIS",
        version=__version__,
        lifespan=lifespan,
        # No interactive docs in production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    # The Next.js browser client polls /health directly (TopBar status light);
    # everything else is fetched server-side. Explicit allow-list from settings —
    # never a wildcard. Added first so CorrelationIdMiddleware stays outermost
    # and even preflight responses carry a correlation id.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(data.router)
    return app


app = create_app()
