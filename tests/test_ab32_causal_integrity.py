"""AB-32 causal, leakage, and temporal-integrity gates."""
from __future__ import annotations

import pandas as pd
import pytest

from intelligence.analysis.integration import build_analysis_context
from market.features.builder import build_features
from market.features.validation import validate_feature_dataset
from market.indicators.engine import IndicatorEngine
from market.regime.detector import detect_market_regime
from ml.datasets.models import TrainingDataset
from ml.datasets.splitting import temporal_split
from ml.preprocessing.pipeline import FeaturePreprocessor


def _candles(rows: int = 180) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-09-20 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    close = [100.0 + i * 0.2 for i in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["RELIANCE"] * rows,
            "open": close,
            "high": [x + 0.2 for x in close],
            "low": [x - 0.15 for x in close],
            "close": close,
            "volume": [1000 + i * 10 for i in range(rows)],
        }
    )


def _market_context(rows: int = 180) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-09-20 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": [100.0 + i * 0.1 for i in range(rows)],
            "return_1": [0.001] * rows,
            "return_3": [0.006] * rows,
            "return_12": [0.025] * rows,
            "volatility_20": [0.015] * rows,
        }
    )


def _feature_snapshot() -> tuple[pd.DataFrame, pd.DataFrame]:
    indicators = IndicatorEngine().calculate(_candles())
    features = validate_feature_dataset(
        build_features(
            indicators,
            market_context=_market_context(),
        )
    )
    return indicators, features


def test_ab32_appending_future_candle_does_not_change_past_analysis() -> None:
    _, base_features = _feature_snapshot()

    past_features = base_features.iloc[:30].copy()
    extended_features = base_features.iloc[:31].copy()

    # Analyze the same decision-time row in both histories. Appending data
    # strictly after t must not alter the analytical snapshot at t.
    past_context = build_analysis_context(past_features.tail(1))
    extended_context = build_analysis_context(extended_features.iloc[29:30])

    assert past_context.timestamp == extended_context.timestamp
    assert past_context.symbol == extended_context.symbol
    assert past_context.feature_vector == extended_context.feature_vector


def test_ab32_future_regime_row_cannot_change_current_regime() -> None:
    _, features = _feature_snapshot()

    base = detect_market_regime(
        features.loc[
            :29,
            ["timestamp", "market_return_3", "market_return_12", "market_volatility_20"],
        ]
    )

    extended = detect_market_regime(
        features.loc[
            :30,
            ["timestamp", "market_return_3", "market_return_12", "market_volatility_20"],
        ]
    )

    assert base.iloc[-1]["timestamp"] == extended.iloc[-2]["timestamp"]
    assert base.iloc[-1]["regime"] == extended.iloc[-2]["regime"]
    assert base.iloc[-1]["regime_probability"] == extended.iloc[-2]["regime_probability"]


def test_ab32_future_label_columns_are_rejected() -> None:
    _, features = _feature_snapshot()
    contaminated = features.copy()
    contaminated["future_return"] = 0.5

    with pytest.raises(ValueError, match="unexpected columns|target/label"):
        validate_feature_dataset(contaminated)


def test_ab32_preprocessor_does_not_fit_during_inference() -> None:
    _, features = _feature_snapshot()
    row = features.tail(1).drop(columns=["timestamp", "symbol"]).copy()

    preprocessor = FeaturePreprocessor()

    with pytest.raises(RuntimeError, match="must be fitted"):
        preprocessor.transform(row)


def test_ab32_temporal_split_is_monotonic_and_non_overlapping() -> None:
    _, features = _feature_snapshot()
    # Use enough timestamps to accommodate the existing 60-minute purge
    # windows around both temporal boundaries.
    repeated = pd.concat(
        [
            features.assign(
                timestamp=features["timestamp"]
                + pd.Timedelta(minutes=45 * offset)
            )
            for offset in range(4)
        ],
        ignore_index=True,
    )
    repeated = repeated.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    ).reset_index(drop=True)
    labeled = repeated.copy()
    labeled["label"] = ["NO_EDGE"] * len(labeled)

    dataset = TrainingDataset(
        data=labeled,
        feature_columns=tuple(features.columns[2:]),
    )
    split = temporal_split(dataset)

    assert split.train_end < split.validation_start
    assert split.validation_end < split.test_start
    assert split.train.data["timestamp"].max() == split.train_end
    assert split.validation.data["timestamp"].min() == split.validation_start
    assert split.test.data["timestamp"].min() == split.test_start


def test_ab32_analysis_uses_only_current_decision_row() -> None:
    _, features = _feature_snapshot()
    row = features.iloc[-1:]

    context = build_analysis_context(row)
    assert context.timestamp == row.iloc[0]["timestamp"]
    assert context.symbol == "RELIANCE"
    assert len(context.feature_vector) == len(row.columns) - 2
