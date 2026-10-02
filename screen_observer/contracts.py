"""Typed contracts for Screen Observer.

The observer is an information producer only. It has no strategy, risk,
safety, broker, or execution authority.

References:
- Screen Intelligence roadmap: S09 Visual-context contract, S11 confidence.
- TRADING_SPECIFICATION.md: causality and timestamp rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .ocr import OCRResult

import pandas as pd


def _timestamp(value: pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise ValueError("screen timestamps must be timezone-aware")
    return ts


@dataclass(frozen=True, slots=True)
class WindowObservation:
    title: str
    application: str
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("window title must not be empty")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("window dimensions must be positive")


@dataclass(frozen=True, slots=True)
class ChartObservation:
    detected: bool
    left: int | None = None
    top: int | None = None
    width: int | None = None
    height: int | None = None
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("chart confidence must be in [0, 1]")
        if self.detected and any(
            value is None for value in (self.left, self.top, self.width, self.height)
        ):
            raise ValueError("detected chart requires a complete region")


@dataclass(frozen=True, slots=True)
class CandleObservation:
    bullish: int = 0
    bearish: int = 0
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.bullish < 0 or self.bearish < 0:
            raise ValueError("candle counts cannot be negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("candle confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ScreenConfidence:
    overall: float
    symbol: float = 0.0
    timeframe: float = 0.0
    chart: float = 0.0
    candles: float = 0.0
    indicators: float = 0.0
    ocr: float = 0.0

    def __post_init__(self) -> None:
        for value in (
            self.overall,
            self.symbol,
            self.timeframe,
            self.chart,
            self.candles,
            self.indicators,
            self.ocr,
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError("screen confidence values must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ScreenObservation:
    observed_at: pd.Timestamp
    image: Any
    windows: tuple[WindowObservation, ...] = ()
    target_window: WindowObservation | None = None
    chart: ChartObservation = field(default_factory=lambda: ChartObservation(False))
    ocr_text: tuple[str, ...] = ()
    symbol: str | None = None
    timeframe: str | None = None
    indicators: tuple[str, ...] = ()
    candles: CandleObservation = field(default_factory=CandleObservation)
    confidence: ScreenConfidence = field(
        default_factory=lambda: ScreenConfidence(overall=0.0)
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at))
        if self.symbol is not None:
            object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "ocr_text", tuple(self.ocr_text))
        object.__setattr__(self, "indicators", tuple(self.indicators))


@dataclass(frozen=True, slots=True)
class VisualContext:
    """Validated visual context passed downstream as observation data."""

    observed_at: pd.Timestamp
    symbol: str | None
    timeframe: str | None
    indicators: tuple[str, ...]
    chart_detected: bool
    candle_observation: CandleObservation
    confidence: ScreenConfidence
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at))
        if self.symbol is not None:
            object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "indicators", tuple(self.indicators))
        object.__setattr__(self, "provenance", dict(self.provenance))

    def as_dict(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at.isoformat(),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "indicators": list(self.indicators),
            "chart_detected": self.chart_detected,
            "candle_bullish": self.candle_observation.bullish,
            "candle_bearish": self.candle_observation.bearish,
            "confidence": {
                "overall": self.confidence.overall,
                "symbol": self.confidence.symbol,
                "timeframe": self.confidence.timeframe,
                "chart": self.confidence.chart,
                "candles": self.confidence.candles,
                "indicators": self.confidence.indicators,
                "ocr": self.confidence.ocr,
            },
            "provenance": dict(self.provenance),
        }
