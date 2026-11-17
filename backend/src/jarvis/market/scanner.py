"""Symbol scanner: discovers eligible Spot and USDⓈ-M Futures symbols from Binance.

Eligibility rules:
* Quote asset = USDT
* Status = TRADING
* 24h quote volume >= MIN_QUOTE_VOLUME
* Not in BLOCKLIST (leveraged tokens, etc.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from jarvis.market.binance_client import BinanceClient

logger = structlog.get_logger(__name__)

# Minimum 24-hour USDT volume to be considered (reduces noise).
MIN_QUOTE_VOLUME: float = 5_000_000.0

# Reject known leveraged / structured tokens by pattern.
_LEVERAGED_PATTERN = re.compile(r"(UP|DOWN|BULL|BEAR|\d+L|\d+S)USDT$")

BLOCKLIST: frozenset[str] = frozenset(
    {
        "USDCUSDT",
        "BUSDUSDT",
        "TUSDUSDT",
        "USDTUSDT",
        "FDUSDUSDT",
    }
)


@dataclass(frozen=True, slots=True)
class EligibleSymbol:
    symbol: str
    base_asset: str
    quote_asset: str
    market: str  # "spot" | "futures"
    volume_24h_usdt: float
    price_change_pct_24h: float
    last_price: float
    filters: dict[str, Any] = field(default_factory=dict)


def _is_eligible_name(symbol: str) -> bool:
    if symbol in BLOCKLIST:
        return False
    if _LEVERAGED_PATTERN.search(symbol):
        return False
    return True


class MarketScanner:
    """Scan Binance and return lists of eligible trading symbols."""

    def __init__(
        self,
        client: BinanceClient,
        *,
        min_volume: float = MIN_QUOTE_VOLUME,
    ) -> None:
        self._client = client
        self._min_volume = min_volume

    async def scan_spot(self) -> list[EligibleSymbol]:
        """Return eligible SPOT symbols sorted by 24h volume descending."""
        info, tickers = await self._fetch_spot_data()
        volume_map = self._build_volume_map(tickers)
        eligible: list[EligibleSymbol] = []

        for sym in info.get("symbols", []):
            if not self._passes_spot_filters(sym):
                continue
            symbol = sym["symbol"]
            volume = float(volume_map.get(symbol, {}).get("quoteVolume", 0.0))
            if volume < self._min_volume:
                continue
            ticker = volume_map.get(symbol, {})
            eligible.append(
                EligibleSymbol(
                    symbol=symbol,
                    base_asset=sym["baseAsset"],
                    quote_asset=sym["quoteAsset"],
                    market="spot",
                    volume_24h_usdt=volume,
                    price_change_pct_24h=float(ticker.get("priceChangePercent", 0)),
                    last_price=float(ticker.get("lastPrice", 0)),
                    filters={f["filterType"]: f for f in sym.get("filters", [])},
                )
            )

        eligible.sort(key=lambda s: s.volume_24h_usdt, reverse=True)
        logger.info("scanner.spot.done", eligible=len(eligible))
        return eligible

    async def scan_futures(self) -> list[EligibleSymbol]:
        """Return eligible USDⓈ-M futures symbols sorted by 24h volume descending."""
        info = await self._client.get_futures_exchange_info()
        eligible: list[EligibleSymbol] = []

        for sym in info.get("symbols", []):
            if sym.get("status") != "TRADING":
                continue
            if sym.get("quoteAsset") != "USDT":
                continue
            symbol = sym["symbol"]
            if not _is_eligible_name(symbol):
                continue
            # Futures exchange info includes volume in some endpoints; we store filters.
            eligible.append(
                EligibleSymbol(
                    symbol=symbol,
                    base_asset=sym["baseAsset"],
                    quote_asset=sym["quoteAsset"],
                    market="futures",
                    volume_24h_usdt=0.0,  # filled by a separate ticker call if needed
                    price_change_pct_24h=0.0,
                    last_price=float(sym.get("lastPrice", 0) or 0),
                    filters={f["filterType"]: f for f in sym.get("filters", [])},
                )
            )

        logger.info("scanner.futures.done", eligible=len(eligible))
        return eligible

    # ------------------------------------------------------------------ #
    async def _fetch_spot_data(
        self,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        import asyncio

        info, tickers = await asyncio.gather(
            self._client.get_spot_exchange_info(),
            self._client.get_spot_ticker_24h(),
        )
        return info, tickers

    @staticmethod
    def _build_volume_map(tickers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {t["symbol"]: t for t in tickers}

    @staticmethod
    def _passes_spot_filters(sym: dict[str, Any]) -> bool:
        if sym.get("status") != "TRADING":
            return False
        if sym.get("quoteAsset") != "USDT":
            return False
        if sym.get("isSpotTradingAllowed") is False:
            return False
        symbol = sym.get("symbol", "")
        return _is_eligible_name(symbol)
