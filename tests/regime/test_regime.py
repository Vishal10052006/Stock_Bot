from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market.regime import MarketRegime, detect_market_regime, validate_regime_dataset


def make_features(n: int = 30) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-08-03 09:15",
        periods=n,
        freq="5min",
        tz="Asia/Kolkata",
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": "AAA",
            "market_return_3": np.full(n, 0.0001),
            "market_return_12": np.full(n, 0.0002),
            "market_volatility_20": np.full(n, 0.01),
        }
    )


def test_warmup_does_not_fabricate_regime() -> None:
    result = detect_market_regime(make_features())
    assert result.loc[:19, "regime"].isna().all()
    assert result.loc[:19, "regime_probability"].isna().all()


def test_trend_up_and_down_are_causal() -> None:
    data = make_features()
    data.loc[21:, "market_return_3"] = 0.001
    data.loc[21:, "market_return_12"] = 0.003
    result = detect_market_regime(data)
    assert result.loc[21, "regime"] == MarketRegime.TREND_UP.value

    data.loc[21:, "market_return_3"] = -0.001
    data.loc[21:, "market_return_12"] = -0.003
    result = detect_market_regime(data)
    assert result.loc[21, "regime"] == MarketRegime.TREND_DOWN.value


def test_high_and_low_volatility_take_precedence() -> None:
    data = make_features()
    data.loc[21, "market_return_3"] = 0.001
    data.loc[21, "market_return_12"] = 0.003
    data.loc[21, "market_volatility_20"] = 0.016
    result = detect_market_regime(data)
    assert result.loc[21, "regime"] == MarketRegime.HIGH_VOLATILITY.value

    data.loc[21, "market_volatility_20"] = 0.007
    result = detect_market_regime(data)
    assert result.loc[21, "regime"] == MarketRegime.LOW_VOLATILITY.value


def test_range_is_used_when_direction_is_weak() -> None:
    data = make_features()
    result = detect_market_regime(data)
    assert result.loc[21, "regime"] == MarketRegime.RANGE.value
    assert 0.5 <= result.loc[21, "regime_probability"] <= 0.999


def test_same_timestamp_market_context_must_agree_across_stocks() -> None:
    data = make_features()
    duplicate = data.copy()
    duplicate["symbol"] = "BBB"
    duplicate.loc[21, "market_return_12"] = 0.99
    data = pd.concat([data, duplicate], ignore_index=True)

    with pytest.raises(ValueError, match="inconsistent market_return_12"):
        detect_market_regime(data)


def test_future_market_changes_do_not_change_past_regimes() -> None:
    data = make_features()
    data.loc[21:25, "market_return_3"] = 0.001
    data.loc[21:25, "market_return_12"] = 0.003
    baseline = detect_market_regime(data)

    perturbed = data.copy()
    perturbed.loc[26:, "market_return_3"] = -0.1
    perturbed.loc[26:, "market_return_12"] = -0.2
    perturbed.loc[26:, "market_volatility_20"] = 1.0
    changed = detect_market_regime(perturbed)

    pd.testing.assert_frame_equal(
        baseline.loc[:25],
        changed.loc[:25],
        check_dtype=False,
    )


def test_validation_accepts_detector_output() -> None:
    result = detect_market_regime(make_features())
    validate_regime_dataset(result)


def test_invalid_probability_is_rejected() -> None:
    data = detect_market_regime(make_features())
    data.loc[21, "regime_probability"] = 1.1
    with pytest.raises(ValueError, match="between 0 and 1"):
        validate_regime_dataset(data)
