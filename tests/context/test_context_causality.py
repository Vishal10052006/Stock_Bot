"""Causality tests for Phase 5 market and sector context."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market.data.context import (
    SectorMapping,
    align_context,
    build_context_returns,
)
from market.data.context.enrichment import enrich_market_sector_context


def _timestamps(periods: int = 16) -> pd.DatetimeIndex:
    return pd.date_range(
        "2026-08-31 09:15",
        periods=periods,
        freq="5min",
        tz="Asia/Kolkata",
    )


def _market_frame(values: list[float]) -> pd.DataFrame:
    timestamps = _timestamps(len(values))
    raw = pd.DataFrame({"timestamp": timestamps, "close": values})
    return build_context_returns(raw)


def test_backward_alignment_never_uses_future_context() -> None:
    observations = pd.DataFrame({
        "timestamp": _timestamps(3),
        "symbol": ["AAA"] * 3,
        "value": [1.0, 2.0, 3.0],
    })
    context = pd.DataFrame({
        "timestamp": _timestamps(3),
        "signal": [10.0, 20.0, 30.0],
    })

    aligned = align_context(
        observations,
        context,
        context_columns=("signal",),
    )

    assert aligned["signal"].tolist() == [10.0, 20.0, 30.0]

    future_only = context.copy()
    future_only.loc[2, "signal"] = 999.0
    altered = align_context(
        observations.iloc[:2],
        future_only,
        context_columns=("signal",),
    )

    assert altered["signal"].tolist() == [10.0, 20.0]


def test_keyed_context_allows_multiple_series_at_same_timestamp() -> None:
    timestamps = _timestamps(3)
    context = pd.DataFrame({
        "timestamp": timestamps.tolist() * 2,
        "sector_index_symbol": ["BANK"] * 3 + ["IT"] * 3,
        "signal": [1.0, 2.0, 3.0, 11.0, 12.0, 13.0],
    }).sort_values(["timestamp", "sector_index_symbol"], kind="stable")

    observations = pd.DataFrame({
        "timestamp": [timestamps[1], timestamps[1]],
        "sector_index_symbol": ["BANK", "IT"],
    }).sort_values(
        ["timestamp", "sector_index_symbol"],
        kind="stable",
    )

    aligned = align_context(
        observations,
        context,
        context_columns=("signal",),
        context_key="sector_index_symbol",
    )

    assert aligned["signal"].tolist() == [2.0, 12.0]


def test_future_context_perturbation_does_not_change_past_features() -> None:
    timestamps = _timestamps(16)
    observations = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": "AAA",
        "close": np.arange(100.0, 116.0),
    })
    market = _market_frame(np.arange(200.0, 216.0))

    baseline = enrich_market_sector_context(
        observations,
        market_context=market,
    )

    perturbed = market.copy()
    perturbed.loc[12:, "close"] *= 100.0
    perturbed = build_context_returns(perturbed[["timestamp", "close"]])

    changed = enrich_market_sector_context(
        observations,
        market_context=perturbed,
    )

    assert baseline.loc[:11, "market_return_1"].equals(
        changed.loc[:11, "market_return_1"]
    )
    assert baseline.loc[:11, "market_volatility_20"].equals(
        changed.loc[:11, "market_volatility_20"]
    )


def test_sector_mapping_is_point_in_time() -> None:
    timestamps = _timestamps(4)
    observations = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": "AAA",
        "close": [100.0, 101.0, 102.0, 103.0],
    })

    sector_values = pd.DataFrame({
        "timestamp": timestamps.tolist() * 2,
        "sector_index_symbol": ["BANK"] * 4 + ["IT"] * 4,
        "close": [100.0, 101.0, 102.0, 103.0] + [200.0, 202.0, 204.0, 206.0],
    }).sort_values(["timestamp", "sector_index_symbol"], kind="stable")
    sector = build_context_returns(
        sector_values,
        key_column="sector_index_symbol",
    )

    mappings = (
        SectorMapping(
            symbol="AAA",
            sector_index_symbol="BANK",
            effective_from=timestamps[0].date(),
            effective_to=timestamps[1].date(),
        ),
        SectorMapping(
            symbol="AAA",
            sector_index_symbol="IT",
            effective_from=timestamps[2].date(),
        ),
    )

    result = enrich_market_sector_context(
        observations,
        market_context=_market_frame([300.0, 301.0, 302.0, 303.0]),
        sector_context=sector,
        sector_mappings=mappings,
    )

    assert result.loc[0, "sector_return_1"] is np.nan or pd.isna(
        result.loc[0, "sector_return_1"]
    )
    assert result.loc[2, "sector_return_1"] == sector.loc[
        (sector["sector_index_symbol"] == "IT")
        & (sector["timestamp"] == timestamps[2]),
        "return_1",
    ].iloc[0]
