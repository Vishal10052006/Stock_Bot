from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market.features.builder import build_features
from market.indicators.engine import IndicatorEngine

from market.data.context import build_context_returns

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


def test_phase5_features_integrate_with_phase6_regime_detector() -> None:
    """Verify the real Phase 4 -> Phase 5 -> Phase 6 pipeline."""

    timestamps = pd.date_range(
        "2026-08-31 09:15",
        periods=80,
        freq="5min",
        tz="Asia/Kolkata",
    )

    # Create deterministic stock OHLCV data for the Phase 4 indicator engine.
    base = np.arange(80, dtype=float)

    stock = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": "TEST",
        "open": 100.0 + base * 0.20,
        "high": 100.5 + base * 0.20,
        "low": 99.5 + base * 0.20,
        "close": 100.0 + base * 0.20,
        "volume": 1000.0 + base * 10.0,
    })

    # Build the actual Phase 4 indicator output.
    indicators = IndicatorEngine().calculate(stock)

    # Build deterministic market-index context through the real Phase 5
    # context-return pipeline.
    market_raw = pd.DataFrame({
        "timestamp": timestamps,
        "close": 200.0 + base * 0.30,
    })

    market_context = build_context_returns(market_raw)

    # Build the actual Phase 5 FeatureDataset, including market context.
    features = build_features(
        indicators,
        market_context=market_context,
    )

    # Phase 5 must expose the fields required by Phase 6.
    assert {
        "timestamp",
        "symbol",
        "market_return_3",
        "market_return_12",
        "market_volatility_20",
    }.issubset(features.columns)

    # Run the actual Phase 6 detector against the Phase 5 output.
    regimes = detect_market_regime(features)

    # The Phase 6 output contract must be exact.
    assert tuple(regimes.columns) == (
        "timestamp",
        "regime",
        "regime_probability",
    )

    # Warm-up rows are allowed to remain unclassified.
    assert regimes["timestamp"].equals(features["timestamp"])

    # After sufficient history, the detector must produce classifications.
    classified = regimes.dropna(subset=["regime"])

    assert not classified.empty

    # Every classified row must contain a valid confidence value.
    assert classified["regime_probability"].between(
        0.0,
        1.0,
    ).all()

    # The complete Phase 6 output must satisfy its validation contract.
    validate_regime_dataset(regimes)
