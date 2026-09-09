"""Causal, rule-based market-regime detection for Phase 6."""
from __future__ import annotations

import numpy as np
import pandas as pd

from market.regime.models import MarketRegime, RegimeConfig, REGIME_OUTPUT_COLUMNS


REQUIRED_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "market_return_3",
    "market_return_12",
    "market_volatility_20",
)


def _validate_input(data: pd.DataFrame) -> None:
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    missing = set(REQUIRED_COLUMNS).difference(data.columns)
    if missing:
        raise ValueError(f"missing required regime columns: {sorted(missing)}")
    if data.empty:
        raise ValueError("data must not be empty")
    if not isinstance(data["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("timestamp must be timezone-aware")
    for column in REQUIRED_COLUMNS[1:]:
        if not pd.api.types.is_numeric_dtype(data[column]):
            raise TypeError(f"{column} must be numeric")


def _market_series(data: pd.DataFrame) -> pd.DataFrame:
    """Collapse a FeatureDataset to one market observation per timestamp."""
    ordered = data.sort_values("timestamp", kind="stable")
    rows: list[dict[str, object]] = []
    for timestamp, group in ordered.groupby("timestamp", sort=False):
        row: dict[str, object] = {"timestamp": timestamp}
        for column in REQUIRED_COLUMNS[1:]:
            values = group[column].dropna().astype(float)
            if values.empty:
                row[column] = np.nan
                continue
            if not np.allclose(
                values.to_numpy(),
                values.iloc[0],
                rtol=0.0,
                atol=1e-12,
            ):
                raise ValueError(
                    f"inconsistent {column} values across stocks at {timestamp}"
                )
            row[column] = float(values.iloc[0])
        rows.append(row)
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


def _confidence(
    regime: MarketRegime,
    *,
    return_3: float,
    return_12: float,
    volatility_ratio: float,
    config: RegimeConfig,
) -> float:
    """Return bounded rule confidence, not a calibrated probability."""
    if regime in (MarketRegime.TREND_UP, MarketRegime.TREND_DOWN):
        magnitude = min(abs(return_12) / config.trend_return_threshold, 1.0)
        confirmation = min(abs(return_3) / config.trend_confirmation_threshold, 1.0)
        return 0.50 + 0.25 * magnitude + 0.25 * confirmation
    if regime is MarketRegime.RANGE:
        directional_quiet = (
            max(0.0, 1.0 - abs(return_12) / config.range_return_threshold)
            if config.range_return_threshold
            else 1.0
        )
        volatility_neutral = max(0.0, 1.0 - abs(np.log(volatility_ratio)))
        return 0.50 + 0.25 * directional_quiet + 0.25 * volatility_neutral
    if regime is MarketRegime.HIGH_VOLATILITY:
        excess = min(
            abs(np.log(volatility_ratio)) / np.log(config.high_volatility_ratio),
            1.0,
        )
        return 0.50 + 0.50 * excess
    compression = min(
        abs(np.log(volatility_ratio)) / abs(np.log(config.low_volatility_ratio)),
        1.0,
    )
    return 0.50 + 0.50 * compression


def _classify(
    return_3: float,
    return_12: float,
    volatility_ratio: float,
    config: RegimeConfig,
) -> MarketRegime:
    """Apply the frozen Phase 6 v1 precedence rules."""
    if volatility_ratio >= config.high_volatility_ratio:
        return MarketRegime.HIGH_VOLATILITY
    if volatility_ratio <= config.low_volatility_ratio:
        return MarketRegime.LOW_VOLATILITY
    if (
        return_12 >= config.trend_return_threshold
        and return_3 >= config.trend_confirmation_threshold
    ):
        return MarketRegime.TREND_UP
    if (
        return_12 <= -config.trend_return_threshold
        and return_3 <= -config.trend_confirmation_threshold
    ):
        return MarketRegime.TREND_DOWN
    return MarketRegime.RANGE


def detect_market_regime(
    features: pd.DataFrame,
    *,
    config: RegimeConfig | None = None,
) -> pd.DataFrame:
    """Detect one causal market regime per timestamp.

    Volatility is compared with a trailing, prior-observation median of
    ``market_volatility_20``. The current volatility value is never used to
    construct its own baseline. No future rows are referenced.

    Rows before a usable volatility baseline are emitted with ``<NA>`` regime
    and ``NaN`` probability rather than fabricating a classification.
    """
    _validate_input(features)
    config = config or RegimeConfig()
    market = _market_series(features)

    market["volatility_baseline"] = (
        market["market_volatility_20"]
        .rolling(
            config.volatility_baseline_window,
            min_periods=config.volatility_baseline_window,
        )
        .median()
        .shift(1)
    )
    market["volatility_ratio"] = market["market_volatility_20"].div(
        market["volatility_baseline"].replace(0.0, np.nan)
    )

    regimes: list[object] = []
    probabilities: list[float] = []
    for row in market.itertuples(index=False):
        values = (
            row.market_return_3,
            row.market_return_12,
            row.market_volatility_20,
            row.volatility_baseline,
            row.volatility_ratio,
        )
        if any(pd.isna(value) for value in values):
            regimes.append(pd.NA)
            probabilities.append(np.nan)
            continue

        regime = _classify(
            float(row.market_return_3),
            float(row.market_return_12),
            float(row.volatility_ratio),
            config,
        )
        confidence = _confidence(
            regime,
            return_3=float(row.market_return_3),
            return_12=float(row.market_return_12),
            volatility_ratio=float(row.volatility_ratio),
            config=config,
        )
        regimes.append(regime.value)
        probabilities.append(max(config.min_probability, min(confidence, 0.999)))

    result = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "regime": pd.Series(regimes, dtype="string"),
            "regime_probability": probabilities,
        }
    )
    return result.loc[:, REGIME_OUTPUT_COLUMNS]


class MarketRegimeDetector:
    """Object-oriented wrapper for the deterministic Phase 6 detector."""

    def __init__(self, config: RegimeConfig | None = None) -> None:
        self.config = config or RegimeConfig()

    def detect(self, features: pd.DataFrame) -> pd.DataFrame:
        return detect_market_regime(features, config=self.config)
