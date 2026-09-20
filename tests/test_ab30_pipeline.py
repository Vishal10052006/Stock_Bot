"""AB-30 clean-branch integration tests."""
from __future__ import annotations

import pandas as pd

from trading.ab30_pipeline import (
    MarketAnalysisPipelineError,
    build_market_analysis,
)


def _candles(rows: int = 40) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-09-20 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    close = [100.0 + index * 0.25 for index in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["RELIANCE"] * rows,
            "open": close,
            "high": [value + 0.20 for value in close],
            "low": [value - 0.15 for value in close],
            "close": close,
            "volume": [1000 + index * 10 for index in range(rows)],
        }
    )


def _market_context(rows: int = 40) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-09-20 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": [100.0] * rows,
            "return_1": [0.001] * rows,
            "return_3": [0.006] * rows,
            "return_12": [0.025] * rows,
            "volatility_20": [0.015] * rows,
        }
    )


def test_ab30_real_market_pipeline_reaches_analysis_context() -> None:
    result = build_market_analysis(
        _candles(),
        symbol="RELIANCE",
        market_context=_market_context(),
    )

    assert len(result.indicators) == 40
    assert len(result.features) == 40
    assert not result.regime.empty
    assert result.analysis.symbol == "RELIANCE"
    assert result.analysis.timestamp == result.features.iloc[-1]["timestamp"]
    assert result.analysis.analysis_version == "v1.0"


def test_ab30_missing_market_context_fails_closed() -> None:
    try:
        build_market_analysis(
            _candles(),
            symbol="RELIANCE",
            market_context=pd.DataFrame(),
        )
    except (MarketAnalysisPipelineError, ValueError):
        pass
    else:
        raise AssertionError("invalid/missing market context must fail closed")
