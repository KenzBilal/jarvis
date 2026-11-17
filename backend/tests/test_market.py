"""Tests — Phase 1: market scanner, indicators, Binance client."""

from __future__ import annotations

import pytest

from jarvis.market.binance_client import BinanceClient, BinanceClientError
from jarvis.market.indicators import (
    Candle,
    IndicatorBundle,
    atr,
    bollinger_bands,
    ema,
    macd,
    parse_candles,
    rsi,
)
from jarvis.market.scanner import (
    BLOCKLIST,
    MarketScanner,
    _is_eligible_name,
)


# ------------------------------------------------------------------ #
# Indicators
# ------------------------------------------------------------------ #

def _closes(n: int, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


def test_rsi_returns_none_for_insufficient_data() -> None:
    result = rsi([100.0] * 5, period=14)
    assert all(v is None for v in result)


def test_rsi_bounded_0_100() -> None:
    closes = _closes(50)
    values = [v for v in rsi(closes, 14) if v is not None]
    assert all(0.0 <= v <= 100.0 for v in values)


def test_rsi_all_up_moves_gives_100() -> None:
    closes = [float(i) for i in range(1, 30)]
    values = [v for v in rsi(closes, 14) if v is not None]
    assert all(v == pytest.approx(100.0) for v in values)


def test_rsi_all_down_moves_gives_0() -> None:
    closes = [float(30 - i) for i in range(30)]
    values = [v for v in rsi(closes, 14) if v is not None]
    assert all(v == pytest.approx(0.0) for v in values)


def test_ema_returns_none_before_period() -> None:
    result = ema(_closes(5), 10)
    assert all(v is None for v in result)


def test_ema_first_value_equals_sma() -> None:
    closes = [float(i) for i in range(1, 11)]
    result = ema(closes, 10)
    assert result[9] == pytest.approx(5.5)


def test_macd_line_fast_minus_slow() -> None:
    closes = _closes(50)
    ml, sl, hist = macd(closes, fast=12, slow=26, signal=9)
    for i, (m, f_e, s_e) in enumerate(zip(ml, ema(closes, 12), ema(closes, 26))):
        if f_e is not None and s_e is not None:
            assert m == pytest.approx(f_e - s_e)


def test_bollinger_middle_is_sma() -> None:
    closes = _closes(30)
    _, mid, _ = bollinger_bands(closes, period=20)
    for i in range(19, len(closes)):
        expected = sum(closes[i - 19: i + 1]) / 20
        assert mid[i] == pytest.approx(expected)


def test_bollinger_upper_above_lower() -> None:
    closes = _closes(30, step=0.5)
    upper, _, lower = bollinger_bands(closes, period=20)
    for u, l in zip(upper, lower):
        if u is not None and l is not None:
            assert u >= l


def _make_candles(n: int) -> list[Candle]:
    return [
        Candle(
            open_time=i * 3600000,
            open=100.0 + i,
            high=102.0 + i,
            low=98.0 + i,
            close=101.0 + i,
            volume=1000.0,
            close_time=(i + 1) * 3600000 - 1,
            quote_volume=101000.0,
            num_trades=500,
        )
        for i in range(n)
    ]


def test_atr_returns_none_for_insufficient_data() -> None:
    result = atr(_make_candles(5), period=14)
    assert all(v is None for v in result)


def test_atr_non_negative() -> None:
    candles = _make_candles(30)
    result = [v for v in atr(candles, 14) if v is not None]
    assert all(v >= 0 for v in result)


def test_indicator_bundle_latest_has_all_keys() -> None:
    candles = _make_candles(60)
    bundle = IndicatorBundle(candles)
    expected_keys = {
        "rsi_14", "ema_20", "ema_50", "macd_line", "macd_signal",
        "macd_hist", "bb_upper", "bb_middle", "bb_lower", "atr_14",
    }
    assert set(bundle.latest.keys()) == expected_keys


def test_parse_candles_converts_binance_format() -> None:
    raw = [[
        1699999200000, "30000.5", "30100.0", "29900.0", "30050.0",
        "150.5", 1699999259999, "4522509.75", 1500,
        "80.3", "2412000.15", "0"
    ]]
    candles = parse_candles(raw)
    assert len(candles) == 1
    assert candles[0].close == pytest.approx(30050.0)
    assert candles[0].num_trades == 1500


# ------------------------------------------------------------------ #
# Scanner eligibility
# ------------------------------------------------------------------ #

def test_blocklist_symbols_rejected() -> None:
    for sym in BLOCKLIST:
        assert _is_eligible_name(sym) is False


def test_leveraged_tokens_rejected() -> None:
    for sym in ["BTCUPUSDT", "ETHDOWNUSDT", "BNBBULLUSDT", "SOL3LUSDT", "BTC3SUSDT"]:
        assert _is_eligible_name(sym) is False, sym


def test_normal_symbols_accepted() -> None:
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]:
        assert _is_eligible_name(sym) is True, sym


def test_scanner_filters_by_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    high_vol_ticker = {
        "symbol": "BTCUSDT", "quoteVolume": "10000000", "lastPrice": "30000",
        "priceChangePercent": "1.5",
    }
    low_vol_ticker = {
        "symbol": "XYZUSDT", "quoteVolume": "100", "lastPrice": "1",
        "priceChangePercent": "0.1",
    }
    mock_info = {
        "symbols": [
            {
                "symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT",
                "baseAsset": "BTC", "isSpotTradingAllowed": True, "filters": [],
            },
            {
                "symbol": "XYZUSDT", "status": "TRADING", "quoteAsset": "USDT",
                "baseAsset": "XYZ", "isSpotTradingAllowed": True, "filters": [],
            },
        ]
    }

    class FakeClient:
        async def get_spot_exchange_info(self):
            return mock_info

        async def get_spot_ticker_24h(self):
            return [high_vol_ticker, low_vol_ticker]

        async def get_futures_exchange_info(self):
            return {"symbols": []}

    scanner = MarketScanner(FakeClient(), min_volume=5_000_000)  # type: ignore[arg-type]
    result = asyncio.run(scanner.scan_spot())
    assert len(result) == 1
    assert result[0].symbol == "BTCUSDT"


def test_scanner_rejects_non_trading_status(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    mock_info = {
        "symbols": [
            {
                "symbol": "BTCUSDT", "status": "BREAK", "quoteAsset": "USDT",
                "baseAsset": "BTC", "isSpotTradingAllowed": True, "filters": [],
            },
        ]
    }

    class FakeClient:
        async def get_spot_exchange_info(self):
            return mock_info

        async def get_spot_ticker_24h(self):
            return [{"symbol": "BTCUSDT", "quoteVolume": "99999999", "lastPrice": "30000", "priceChangePercent": "1"}]

        async def get_futures_exchange_info(self):
            return {"symbols": []}

    scanner = MarketScanner(FakeClient(), min_volume=0)  # type: ignore[arg-type]
    result = asyncio.run(scanner.scan_spot())
    assert result == []


# ------------------------------------------------------------------ #
# BinanceClient rate limit / weight tracking
# ------------------------------------------------------------------ #

def test_binance_client_weight_tracking() -> None:
    import asyncio
    import time

    client = BinanceClient()
    client._weight_reset_at = time.monotonic() + 60
    client._weight_used = 0

    # Should not sleep when well under threshold
    async def run():
        await client._maybe_throttle(100)

    asyncio.run(run())
    assert client._weight_used == 0  # weight only updated from response headers
