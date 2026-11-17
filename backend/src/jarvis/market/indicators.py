"""Technical indicators computed from OHLCV candle data.

All functions operate on plain Python lists (from Binance klines response)
and return float or list[float | None]. No external TA library required.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class Candle(NamedTuple):
    open_time: int    # ms timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int   # ms timestamp
    quote_volume: float
    num_trades: int


def parse_candles(raw: list[list]) -> list[Candle]:
    """Convert Binance klines response to typed Candle list."""
    return [
        Candle(
            open_time=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            close_time=int(row[6]),
            quote_volume=float(row[7]),
            num_trades=int(row[8]),
        )
        for row in raw
    ]


# ------------------------------------------------------------------ #
# RSI
# ------------------------------------------------------------------ #

def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index (Wilder's smoothing)."""
    result: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return result

    gains, losses = [], []
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period, len(closes)):
        if i > period:
            delta = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period

        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


# ------------------------------------------------------------------ #
# EMA / MACD
# ------------------------------------------------------------------ #

def ema(values: list[float], period: int) -> list[float | None]:
    """Exponential Moving Average."""
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result

    k = 2.0 / (period + 1)
    # Seed with simple MA
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    prev = seed

    for i in range(period, len(values)):
        curr = values[i] * k + prev * (1 - k)
        result[i] = curr
        prev = curr

    return result


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD line, signal line, histogram."""
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)

    macd_line: list[float | None] = [
        (f - s) if f is not None and s is not None else None
        for f, s in zip(fast_ema, slow_ema)
    ]

    # Signal EMA over non-None MACD values
    macd_values = [v for v in macd_line if v is not None]
    if len(macd_values) < signal:
        signal_line: list[float | None] = [None] * len(closes)
        histogram: list[float | None] = [None] * len(closes)
        return macd_line, signal_line, histogram

    signal_values = ema(macd_values, signal)
    # Re-align into full-length list
    none_prefix = next(i for i, v in enumerate(macd_line) if v is not None)
    signal_line = [None] * none_prefix + signal_values  # type: ignore[operator]

    histogram = [
        (m - s) if m is not None and s is not None else None
        for m, s in zip(macd_line, signal_line)
    ]
    return macd_line, signal_line, histogram


# ------------------------------------------------------------------ #
# Bollinger Bands
# ------------------------------------------------------------------ #

def bollinger_bands(
    closes: list[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Upper, middle (SMA), lower Bollinger Bands."""
    upper: list[float | None] = [None] * len(closes)
    middle: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        sd = math.sqrt(variance)
        upper[i] = sma + std_dev * sd
        middle[i] = sma
        lower[i] = sma - std_dev * sd

    return upper, middle, lower


# ------------------------------------------------------------------ #
# ATR
# ------------------------------------------------------------------ #

def atr(candles: list[Candle], period: int = 14) -> list[float | None]:
    """Average True Range (Wilder's smoothing)."""
    result: list[float | None] = [None] * len(candles)
    if len(candles) < period + 1:
        return result

    def true_range(i: int) -> float:
        h = candles[i].high
        l = candles[i].low
        prev_c = candles[i - 1].close
        return max(h - l, abs(h - prev_c), abs(l - prev_c))

    trs = [true_range(i) for i in range(1, len(candles))]
    avg = sum(trs[:period]) / period
    result[period] = avg

    for i in range(period + 1, len(candles)):
        avg = (avg * (period - 1) + trs[i - 1]) / period
        result[i] = avg

    return result


# ------------------------------------------------------------------ #
# Convenience bundle
# ------------------------------------------------------------------ #

class IndicatorBundle:
    """All indicators for a single symbol/timeframe, computed once."""

    def __init__(self, candles: list[Candle]) -> None:
        closes = [c.close for c in candles]
        self.candles = candles
        self.rsi_14 = rsi(closes, 14)
        self.ema_20 = ema(closes, 20)
        self.ema_50 = ema(closes, 50)
        self.macd_line, self.macd_signal, self.macd_hist = macd(closes)
        self.bb_upper, self.bb_middle, self.bb_lower = bollinger_bands(closes)
        self.atr_14 = atr(candles, 14)

    @property
    def latest(self) -> dict[str, float | None]:
        """Most recent indicator values (last index)."""
        return {
            "rsi_14": self.rsi_14[-1],
            "ema_20": self.ema_20[-1],
            "ema_50": self.ema_50[-1],
            "macd_line": self.macd_line[-1],
            "macd_signal": self.macd_signal[-1],
            "macd_hist": self.macd_hist[-1],
            "bb_upper": self.bb_upper[-1],
            "bb_middle": self.bb_middle[-1],
            "bb_lower": self.bb_lower[-1],
            "atr_14": self.atr_14[-1],
        }
