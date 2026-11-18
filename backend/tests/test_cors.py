"""CORS: browser origins are an explicit allow-list — never a wildcard.

The Next.js browser client polls ``/health`` directly (TopBar status light);
all other frontend access is server-side and sends no Origin header.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from jarvis.api.main import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_allowed_origin_is_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


async def test_disallowed_origin_gets_no_cors_header(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None


async def test_server_side_calls_are_unaffected(client: httpx.AsyncClient) -> None:
    # No Origin header (server-side fetch, curl, tests) → plain response, no CORS noise.
    response = await client.get("/health")
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_preflight_for_disallowed_origin_is_not_granted(client: httpx.AsyncClient) -> None:
    response = await client.request(
        "OPTIONS",
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") is None
