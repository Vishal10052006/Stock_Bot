"""Structured visual evidence contracts for Screen Observer S06-S08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CandleVisualEvidence:
    bullish: int = 0
    bearish: int = 0
    total: int = 0
    confidence: float = 0.0
    chart_region: tuple[int, int, int, int] | None = None

    def __post_init__(self) -> None:
        if min(self.bullish, self.bearish, self.total) < 0:
            raise ValueError("candle evidence counts cannot be negative")
        if self.total != self.bullish + self.bearish:
            raise ValueError("candle total must equal bullish + bearish")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("candle evidence confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class IndicatorEvidence:
    name: str
    confidence: float
    source: str = "ocr"
    bbox: tuple[int, int, int, int] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("indicator name must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("indicator confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class TimeframeEvidence:
    value: str
    confidence: float
    source: str = "ocr"
    bbox: tuple[int, int, int, int] | None = None

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("timeframe value must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("timeframe confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ScreenAnalysisContext:
    observed_at: Any
    market_symbol: str
    market_timeframe: str
    screen_symbol: str | None
    screen_timeframe: str | None
    indicators: tuple[str, ...]
    candles: CandleVisualEvidence
    confidence: Any
    reconciliation_status: str
    reconciliation_reasons: tuple[str, ...]
    usable: bool
    provenance: dict[str, str]

    def __post_init__(self) -> None:
        if not self.market_symbol.strip():
            raise ValueError("market_symbol must not be empty")
        if not self.market_timeframe.strip():
            raise ValueError("market_timeframe must not be empty")
        object.__setattr__(self, "indicators", tuple(self.indicators))
        object.__setattr__(self, "reconciliation_reasons", tuple(self.reconciliation_reasons))
        object.__setattr__(self, "provenance", dict(self.provenance))

    def as_dict(self) -> dict[str, Any]:
        return {
            "observed_at": str(self.observed_at),
            "market_symbol": self.market_symbol,
            "market_timeframe": self.market_timeframe,
            "screen_symbol": self.screen_symbol,
            "screen_timeframe": self.screen_timeframe,
            "indicators": list(self.indicators),
            "candles": {
                "bullish": self.candles.bullish,
                "bearish": self.candles.bearish,
                "total": self.candles.total,
                "confidence": self.candles.confidence,
            },
            "confidence": self.confidence,
            "reconciliation_status": self.reconciliation_status,
            "reconciliation_reasons": list(self.reconciliation_reasons),
            "usable": self.usable,
            "provenance": dict(self.provenance),
        }
