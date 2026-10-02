"""S12 screen-aware analysis context.

This module combines visual evidence with market identity/timeframe
reconciliation. It is explicitly observation-only: it produces context and
quality gates, never a trade signal, order, position size, or risk approval.
"""

from __future__ import annotations

import pandas as pd

from .confidence import screen_is_usable
from .contracts import ScreenObservation
from .evidence import CandleVisualEvidence, ScreenAnalysisContext
from .reconciliation import reconcile
from .validation import validate_screen_observation


def build_screen_analysis_context(
    observation: ScreenObservation,
    *,
    market_symbol: str,
    market_timeframe: str,
    decision_timestamp: pd.Timestamp,
    max_age_seconds: float = 30.0,
    minimum_confidence: float = 0.55,
) -> ScreenAnalysisContext:
    from .context import build_visual_context

    context = build_visual_context(observation)
    reconciliation = reconcile(
        context,
        market_symbol=market_symbol,
        market_timeframe=market_timeframe,
        decision_timestamp=decision_timestamp,
        max_age_seconds=max_age_seconds,
    )

    validation = validate_screen_observation(
        observation,
        require_chart=True,
        require_symbol=True,
        require_timeframe=True,
        minimum_overall_confidence=minimum_confidence,
    )

    candles = CandleVisualEvidence(
        bullish=observation.candles.bullish,
        bearish=observation.candles.bearish,
        total=observation.candles.bullish + observation.candles.bearish,
        confidence=observation.candles.confidence,
        chart_region=(
            (observation.chart.left, observation.chart.top,
             observation.chart.width, observation.chart.height)
            if observation.chart.detected else None
        ),
    )

    usable = (
        reconciliation.usable
        and validation.usable
        and screen_is_usable(
            observation.confidence,
            minimum_overall=minimum_confidence,
        )
    )

    return ScreenAnalysisContext(
        observed_at=observation.observed_at,
        market_symbol=market_symbol.strip().upper(),
        market_timeframe=market_timeframe,
        screen_symbol=observation.symbol,
        screen_timeframe=observation.timeframe,
        indicators=observation.indicators,
        candles=candles,
        confidence=observation.confidence,
        reconciliation_status=(reconciliation.status if validation.usable else "INVALID"),
        reconciliation_reasons=tuple(reconciliation.reasons) + tuple(validation.reasons),
        usable=usable,
        provenance={
            "source": "desktop_screen",
            "authority": "OBSERVATION_ONLY",
            "module": "screen_aware_analysis",
            "market_authority": "MARKET_FEED",
        },
    )
