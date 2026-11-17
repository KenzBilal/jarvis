"""API behaviour: liveness, readiness (fail closed), correlation ids, error envelope, retries, workers."""

import json
import logging
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from jarvis.api.main import create_app
from jarvis.config.settings import get_settings
from jarvis.core import errors
from jarvis.core.errors import RetryExhaustedError, retry_async
from jarvis.core.logging import REDACTED, redact_sensitive
from jarvis.db import base as db


@pytest.fixture
def app() -> FastAPI:
    application = create_app()

    @application.get("/_boom")
    async def boom() -> None:  # pragma: no cover - body runs via the client
        raise RuntimeError("password=hunter2 exploded")

    @application.get("/_app_error")
    async def app_error() -> None:
        raise errors.NotFoundError(details={"x": 1})

    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_probes(monkeypatch: pytest.MonkeyPatch, *, database: bool, redis: bool) -> None:
    async def fake_db() -> bool:
        return database

    async def fake_redis() -> bool:
        return redis

    monkeypatch.setattr(db, "check_database", fake_db)
    monkeypatch.setattr(db, "check_redis", fake_redis)


# --------------------------------------------------------------------------- #
# /health and /ready
# --------------------------------------------------------------------------- #
async def test_health_is_live_without_dependencies(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["trading_mode"] == "paper"
    assert body["env"] == "test"


async def test_ready_ok_when_all_dependencies_up(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probes(monkeypatch, database=True, redis=True)
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


@pytest.mark.parametrize(("database", "redis"), [(False, True), (True, False), (False, False)])
async def test_ready_fails_closed_if_any_dependency_down(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, database: bool, redis: bool
) -> None:
    _patch_probes(monkeypatch, database=database, redis=redis)
    response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == ("ok" if database else "unavailable")
    assert body["checks"]["redis"] == ("ok" if redis else "unavailable")


async def test_real_probes_fail_closed_on_broken_clients() -> None:
    class BrokenRedis:
        async def ping(self) -> bool:
            raise ConnectionError("redis://:topsecret@nowhere")

    class BrokenEngine:
        def connect(self) -> None:
            raise ConnectionError("postgresql://u:topsecret@nowhere/db")

    assert await db.check_redis(BrokenRedis()) is False  # type: ignore[arg-type]
    assert await db.check_database(BrokenEngine()) is False  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Correlation ids & error handling
# --------------------------------------------------------------------------- #
async def test_correlation_id_generated_and_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert len(response.headers["X-Correlation-ID"]) == 32


async def test_safe_client_correlation_id_is_propagated(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Correlation-ID": "req-123.abc"})
    assert response.headers["X-Correlation-ID"] == "req-123.abc"


async def test_unsafe_client_correlation_id_is_replaced(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Correlation-ID": "bad id\twith spaces"})
    assert response.headers["X-Correlation-ID"] != "bad id\twith spaces"
    assert len(response.headers["X-Correlation-ID"]) == 32


async def test_unknown_route_uses_error_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["correlation_id"] == response.headers["X-Correlation-ID"]


async def test_application_error_uses_public_message(client: httpx.AsyncClient) -> None:
    response = await client.get("/_app_error")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == errors.NotFoundError.public_message


async def test_unhandled_exception_fails_closed_without_leaking(client: httpx.AsyncClient) -> None:
    response = await client.get("/_boom")
    assert response.status_code == 500
    assert "hunter2" not in response.text
    assert "exploded" not in response.text
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert error["correlation_id"] == response.headers["X-Correlation-ID"]


async def test_openapi_available_outside_production(client: httpx.AsyncClient) -> None:
    assert (await client.get("/openapi.json")).status_code == 200


# --------------------------------------------------------------------------- #
# Retry with exponential backoff
# --------------------------------------------------------------------------- #
@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(errors, "_sleep", fake_sleep)
    return recorded


async def test_retry_succeeds_after_transient_failures(sleeps: list[float]) -> None:
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("transient")
        return "ok"

    assert await retry_async(flaky, attempts=5, base_delay=1.0, jitter=False) == "ok"
    assert calls == 3
    assert sleeps == [1.0, 2.0]  # exponential: base * 2**(n-1)


async def test_retry_caps_delay(sleeps: list[float]) -> None:
    async def always_fails() -> None:
        raise ConnectionError("down")

    with pytest.raises(RetryExhaustedError):
        await retry_async(always_fails, attempts=5, base_delay=1.0, max_delay=3.0, jitter=False)
    assert sleeps == [1.0, 2.0, 3.0, 3.0]


async def test_retry_exhaustion_is_chained_and_fail_closed(sleeps: list[float]) -> None:
    async def always_fails() -> None:
        raise ConnectionError("down")

    with pytest.raises(RetryExhaustedError) as excinfo:
        await retry_async(always_fails, attempts=2, operation="demo")
    assert isinstance(excinfo.value.__cause__, ConnectionError)
    assert excinfo.value.attempts == 2
    assert len(sleeps) == 1


async def test_retry_does_not_catch_unlisted_exceptions(sleeps: list[float]) -> None:
    async def wrong() -> None:
        raise KeyError("x")

    with pytest.raises(KeyError):
        await retry_async(wrong, retry_on=(ConnectionError,))
    assert sleeps == []


async def test_retry_jitter_stays_within_bounds(sleeps: list[float]) -> None:
    async def always_fails() -> None:
        raise ConnectionError("down")

    with pytest.raises(RetryExhaustedError):
        await retry_async(always_fails, attempts=3, base_delay=2.0, jitter=True)
    assert 1.0 <= sleeps[0] <= 2.0
    assert 2.0 <= sleeps[1] <= 4.0


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def test_redaction_masks_keys_and_url_credentials() -> None:
    event = {
        "event": "x",
        "password": "p",
        "nested": {"api_key": "k", "ok": "fine"},
        "dsn_text": "postgresql://user:hunter2@host/db",
        "items": ["redis://:abc@h:6379"],
    }
    cleaned = redact_sensitive(None, "info", event)
    assert cleaned["password"] == REDACTED
    assert cleaned["nested"] == {"api_key": REDACTED, "ok": "fine"}
    assert "hunter2" not in json.dumps(cleaned)
    assert "abc" not in json.dumps(cleaned)


def test_logs_are_json_with_correlation_id_and_no_secrets(capsys: pytest.CaptureFixture[str]) -> None:
    import structlog

    from jarvis.core.logging import configure_logging, correlation_context

    configure_logging("INFO", environment="test")
    with correlation_context("cid-1"):
        structlog.get_logger("t").info("hello", password="x", url="postgresql://u:hunter2@h/db")
        logging.getLogger("stdlib.t").warning("from stdlib")
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert lines[0]["event"] == "hello"
    assert lines[0]["correlation_id"] == "cid-1"
    assert lines[0]["service"] == "jarvis"
    assert lines[0]["password"] == REDACTED
    assert "hunter2" not in json.dumps(lines)
    assert lines[1]["event"] == "from stdlib"
    assert lines[1]["correlation_id"] == "cid-1"


# --------------------------------------------------------------------------- #
# Worker
# --------------------------------------------------------------------------- #
async def test_worker_heartbeat_writes_ttl_key() -> None:
    from jarvis.workers.tasks import HEARTBEAT_KEY, HEARTBEAT_TTL_SECONDS, WorkerSettings, heartbeat

    class FakeRedis:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, int]] = []

        async def set(self, key: str, value: str, ex: int) -> bool:
            self.calls.append((key, value, ex))
            return True

    fake = FakeRedis()
    stamp = await heartbeat({"redis": fake, "job_try": 1})
    assert fake.calls == [(HEARTBEAT_KEY, stamp, HEARTBEAT_TTL_SECONDS)]
    assert heartbeat in WorkerSettings.functions
    assert WorkerSettings.redis_settings.port == 6379


async def test_worker_startup_runs_in_paper_mode() -> None:
    from jarvis.workers.tasks import on_startup

    ctx: dict[str, object] = {}
    await on_startup(ctx)
    assert "started_monotonic" in ctx
    assert get_settings().trading_mode == "paper"
