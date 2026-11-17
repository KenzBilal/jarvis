"""Thin async Binance public REST client.

Covers only public (unauthenticated) endpoints used in Phase 1.
Signed/authenticated endpoints are added in Phase 8 (execution engine only).

Rate-limit handling:
* Respects ``X-MBX-USED-WEIGHT-1M`` header; backs off when >80% of 1200 rpm.
* On HTTP 429 / 418, waits ``Retry-After`` seconds then retries.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from jarvis.core.errors import DependencyUnavailableError, retry_async

logger = structlog.get_logger(__name__)

SPOT_BASE = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"

# Binance allows 1200 request-weight/min; we back off at 80%.
_WEIGHT_LIMIT = 1200
_WEIGHT_BACKOFF_THRESHOLD = 0.8
_BACKOFF_SLEEP = 10.0  # seconds to sleep when near weight limit


class BinanceClientError(DependencyUnavailableError):
    code = "binance_error"
    public_message = "Binance API request failed."


class BinanceClient:
    """Async Binance REST client for public endpoints."""

    def __init__(
        self,
        *,
        spot_base: str = SPOT_BASE,
        futures_base: str = FUTURES_BASE,
        timeout: float = 10.0,
    ) -> None:
        self._spot_base = spot_base
        self._futures_base = futures_base
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._weight_used: int = 0
        self._weight_reset_at: float = 0.0

    async def __aenter__(self) -> "BinanceClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def get_spot_exchange_info(self) -> dict[str, Any]:
        """Return full exchange info (symbols, filters, rate limits)."""
        return await self._get(self._spot_base, "/api/v3/exchangeInfo", weight=20)

    async def get_futures_exchange_info(self) -> dict[str, Any]:
        """Return USDⓈ-M futures exchange info."""
        return await self._get(self._futures_base, "/fapi/v1/exchangeInfo", weight=1)

    async def get_spot_ticker_24h(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """24-hour price stats. No symbol = all symbols (weight=80)."""
        params = {"symbol": symbol} if symbol else {}
        weight = 2 if symbol else 80
        result = await self._get(self._spot_base, "/api/v3/ticker/24hr", params=params, weight=weight)
        return result if isinstance(result, list) else [result]

    async def get_spot_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> list[list[Any]]:
        """OHLCV candles for a spot symbol."""
        return await self._get(
            self._spot_base,
            "/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            weight=2,
        )

    async def get_futures_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> list[list[Any]]:
        """OHLCV candles for a USDⓈ-M futures symbol."""
        return await self._get(
            self._futures_base,
            "/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            weight=1,
        )

    async def get_spot_order_book_ticker(self, symbol: str) -> dict[str, Any]:
        """Best bid/ask for a spot symbol (weight=2)."""
        return await self._get(
            self._spot_base,
            "/api/v3/ticker/bookTicker",
            params={"symbol": symbol},
            weight=2,
        )

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    async def _get(
        self,
        base: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        weight: int = 1,
    ) -> Any:
        await self._maybe_throttle(weight)

        async def _do() -> Any:
            assert self._client is not None, "Use as async context manager"
            url = f"{base}{path}"
            response = await self._client.get(url, params=params)
            self._update_weight(response)

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "10"))
                logger.warning("binance.rate_limited", retry_after=retry_after, path=path)
                await asyncio.sleep(retry_after)
                raise BinanceClientError("Rate limited by Binance")

            if response.status_code == 418:
                retry_after = float(response.headers.get("Retry-After", "60"))
                logger.error("binance.ip_banned", retry_after=retry_after)
                await asyncio.sleep(retry_after)
                raise BinanceClientError("IP banned by Binance")

            if response.status_code >= 400:
                logger.warning(
                    "binance.http_error",
                    status=response.status_code,
                    path=path,
                    body=response.text[:200],
                )
                raise BinanceClientError(f"Binance HTTP {response.status_code}")

            return response.json()

        return await retry_async(
            _do,
            attempts=3,
            base_delay=0.5,
            retry_on=(BinanceClientError, httpx.TransportError),
            operation=f"binance.get{path}",
        )

    def _update_weight(self, response: httpx.Response) -> None:
        raw = response.headers.get("X-MBX-USED-WEIGHT-1M")
        if raw and raw.isdigit():
            self._weight_used = int(raw)
            self._weight_reset_at = time.monotonic() + 60.0

    async def _maybe_throttle(self, weight: int) -> None:
        now = time.monotonic()
        if now > self._weight_reset_at:
            self._weight_used = 0
        projected = self._weight_used + weight
        if projected >= _WEIGHT_LIMIT * _WEIGHT_BACKOFF_THRESHOLD:
            wait = max(0.0, self._weight_reset_at - now)
            logger.info("binance.throttling", wait_seconds=round(wait, 1), weight_used=self._weight_used)
            await asyncio.sleep(wait or _BACKOFF_SLEEP)
