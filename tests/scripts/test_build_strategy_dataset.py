from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.trading.build_strategy_dataset import (
    STRATEGY_READY_COLUMNS,
    build_strategy_dataset,
)


def _frames(rows: int = 1000) -> tuple[pd.DataFrame, pd.DataFrame]:
    timestamps = pd.date_range(
        "2026-01-05 03:45:00+00:00",
        periods=rows,
        freq="5min",
    )

    def make(symbol: str, offset: float) -> pd.DataFrame:
        close = 100.0 + offset + np.arange(rows, dtype=float) * 0.03
        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "symbol": symbol,
                "open": close - 0.05,
                "high": close + 0.20,
                "low": close - 0.20,
                "close": close,
                "volume": 1000.0 + np.arange(rows) * 2.0,
            }
        )

    return make("RELIANCE", 0.0), make("NIFTY 50", 100.0)


def test_build_strategy_dataset_has_complete_causal_decision_schema() -> None:
    stocks, market = _frames()

    result = build_strategy_dataset(stocks, market)

    assert tuple(result.columns) == STRATEGY_READY_COLUMNS
    assert not result.empty
    assert result["symbol"].eq("RELIANCE").all()
    assert result["timestamp"].is_monotonic_increasing
    assert not result.duplicated(["symbol", "timestamp"]).any()

    for column in (
        "regime_probability",
        "vwap_distance_pct",
        "rvol_20",
        "atr_14",
        "swing_high",
        "swing_low",
        "support_20",
        "resistance_20",
    ):
        assert np.isfinite(result[column].to_numpy(dtype=float)).all()

    assert result["regime_probability"].between(0.0, 1.0).all()


def test_candidate_inputs_are_causal() -> None:
    stocks, market = _frames()
    baseline = build_strategy_dataset(stocks, market)

    changed_stocks = stocks.copy()
    changed_market = market.copy()

    cutoff = 700
    changed_stocks.loc[cutoff:, ["open", "high", "low", "close", "volume"]] *= 4.0
    changed_market.loc[cutoff:, ["open", "high", "low", "close", "volume"]] *= 0.25

    changed = build_strategy_dataset(changed_stocks, changed_market)

    common = baseline.merge(
        changed,
        on=["timestamp", "symbol"],
        how="inner",
        suffixes=("_before", "_after"),
        validate="one_to_one",
    )

    prefix = common.loc[
        common["timestamp"] < stocks.loc[cutoff, "timestamp"]
    ]

    assert not prefix.empty

    for column in (
        "close",
        "regime",
        "regime_probability",
        "vwap_distance_pct",
        "rvol_20",
        "higher_high",
        "higher_low",
        "lower_low",
        "lower_high",
        "atr_14",
        "swing_high",
        "swing_low",
        "support_20",
        "resistance_20",
    ):
        left = prefix[f"{column}_before"]
        right = prefix[f"{column}_after"]

        if pd.api.types.is_bool_dtype(left) or str(left.dtype) == "boolean":
            pd.testing.assert_series_equal(
                left.reset_index(drop=True),
                right.reset_index(drop=True),
                check_names=False,
            )
        elif pd.api.types.is_numeric_dtype(left):
            np.testing.assert_allclose(
                left.to_numpy(dtype=float),
                right.to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-12,
                equal_nan=True,
            )
        else:
            pd.testing.assert_series_equal(
                left.reset_index(drop=True),
                right.reset_index(drop=True),
                check_names=False,
            )


def test_missing_nifty_benchmark_fails_closed() -> None:
    stocks, _ = _frames()
    bad_market = stocks.assign(symbol="BANKNIFTY")

    with pytest.raises(ValueError, match="NIFTY 50 benchmark"):
        build_strategy_dataset(stocks, bad_market)
