"""Liveness (/health) and readiness (/ready) endpoints."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from jarvis import __version__
from jarvis.config.settings import get_settings
from jarvis.db import base as db

router = APIRouter(tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"]
    version: str
    env: str
    trading_mode: str


class ReadyChecks(BaseModel):
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    checks: ReadyChecks


@router.get("/health", response_model=LiveResponse, summary="Liveness probe (no dependencies)")
async def health() -> LiveResponse:
    settings = get_settings()
    return LiveResponse(
        status="ok",
        version=__version__,
        env=settings.jarvis_env,
        trading_mode=settings.trading_mode,
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadyResponse}},
    summary="Readiness probe (Postgres + Redis)",
)
async def ready(response: Response) -> ReadyResponse:
    # Looked up on the module at call time so tests can substitute the probes.
    database_ok, redis_ok = await asyncio.gather(db.check_database(), db.check_redis())
    checks = ReadyChecks(
        database="ok" if database_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
    )
    if database_ok and redis_ok:
        return ReadyResponse(status="ready", checks=checks)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(status="unavailable", checks=checks)
