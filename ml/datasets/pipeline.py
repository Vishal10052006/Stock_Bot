"""
Real historical-data pipeline for Phase 9 supervised learning.

Pipeline:

    Historical OHLCV
        -> Indicators
        -> Features
        -> Market Regime
        -> Directional Candidates
        -> Phase 7 Decision Labels
        -> TrainingDataset

The pipeline is deliberately separate from Phase 8 BaselineStrategy.
Phase 8 is a benchmark strategy; it must not condition the ML target
dataset.

Causality:
    - Indicators/features use information available at decision time.
    - Candidates use decision-time information only.
    - Future OHLC is accessed only by Phase 7 labeling.
    - The final TrainingDataset contains only causal features + label.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from market.indicators.engine import IndicatorEngine
from market.features.builder import build_features
from market.regime.detector import detect_market_regime
from market.data.context.models import SectorMapping
from market.data.historical.models import HistoricalDataset

from trading.signals import (
    CandidateConfig,
    build_directional_candidates,
)
from ml.labeling import (
    DecisionLabelingOutcome,
    LabelingConfig,
    label_decision,
)
from ml.datasets.builder import build_training_dataset
from ml.datasets.models import TrainingDataset


@dataclass(frozen=True, slots=True)
class Phase9DatasetResult:
    """
    Result of real historical Phase 9 dataset construction.

    training_dataset:
        Final leakage-safe supervised-learning dataset.

    feature_rows:
        Number of decision-time feature observations before
        candidate eligibility filtering.

    eligible_rows:
        Number of observations for which both LONG and SHORT
        candidates could be constructed.

    excluded_rows:
        Feature observations excluded because the decision
        observation could not receive a complete supervised label.

    exclusion_reasons:
        Auditable counts of why observations were excluded.

    labels:
        Auditable decision-level labeling outcomes.
    """

    training_dataset: TrainingDataset
    feature_rows: int
    eligible_rows: int
    excluded_rows: int
    exclusion_reasons: tuple[tuple[str, int], ...]
    labels: tuple[DecisionLabelingOutcome, ...]

    # Decision-time-only context retained separately from the frozen ML
    # feature matrix so Phase 9 can benchmark the frozen Phase 8 strategy
    # without adding strategy features to TrainingDataset v1.
    strategy_context: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def label_distribution(self) -> pd.Series:
        """Return the final decision-label distribution."""
        return self.training_dataset.y.value_counts().sort_index()


def _candles_to_frame(dataset: HistoricalDataset) -> pd.DataFrame:
    """Convert canonical HistoricalDataset candles to OHLCV DataFrame."""

    rows = [
        {
            "timestamp": candle.timestamp,
            "symbol": candle.symbol,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in dataset.bars
    ]

    if not rows:
        raise ValueError("HistoricalDataset contains no candles")

    return pd.DataFrame(rows)


def _validate_candle_frame(candles: pd.DataFrame) -> None:
    """Validate the minimum chronological candle contract."""

    required = {
        "timestamp",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = required.difference(candles.columns)

    if missing:
        raise ValueError(
            f"candle frame is missing required columns: {sorted(missing)}"
        )

    if candles.empty:
        raise ValueError("candle frame must not be empty")

    if not isinstance(candles["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("candle timestamps must be timezone-aware")

    ordered = candles.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    )

    if ordered.duplicated(
        ["symbol", "timestamp"],
        keep=False,
    ).any():
        raise ValueError(
            "candle frame contains duplicate symbol/timestamp observations"
        )


def _build_labels(
    *,
    candles: pd.DataFrame,
    decision_rows: pd.DataFrame,
    candidate_config: CandidateConfig,
    labeling_config: LabelingConfig,
) -> tuple[
    list[DecisionLabelingOutcome],
    int,
    tuple[tuple[str, int], ...],
]:
    """
    Build both directional candidates and label eligible observations.

    A row is eligible only when:

        1. Both LONG and SHORT candidates can be constructed.
        2. The full Phase 7 future horizon is available.

    Rows failing either condition are excluded from the supervised
    training dataset. They are never assigned a fabricated NO_EDGE label.
    """

    outcomes: list[DecisionLabelingOutcome] = []

    exclusion_reasons = {
        "CANDIDATE_CONSTRUCTION_FAILURE": 0,
        "MISSING_SYMBOL_CANDLES": 0,
        "INSUFFICIENT_FUTURE_BARS": 0,
    }

    # Normalize candles once for efficient future-horizon checks.
    candles_by_symbol = {
        str(symbol): group.sort_values(
            "timestamp",
            kind="stable",
        )
        for symbol, group in candles.groupby(
            candles["symbol"].astype(str),
            sort=False,
        )
    }

    for _, row in decision_rows.iterrows():
        try:
            long_candidate, short_candidate = (
                build_directional_candidates(
                    row,
                    config=candidate_config,
                )
            )
        except (TypeError, ValueError):
            exclusion_reasons["CANDIDATE_CONSTRUCTION_FAILURE"] += 1
            continue

        # A complete label requires the full future horizon.
        symbol_candles = candles_by_symbol.get(
            long_candidate.symbol
        )

        if symbol_candles is None:
            exclusion_reasons["MISSING_SYMBOL_CANDLES"] += 1
            continue

        future_count = int(
            (
                symbol_candles["timestamp"]
                > long_candidate.timestamp
            ).sum()
        )

        if future_count < labeling_config.horizon_bars:
            exclusion_reasons["INSUFFICIENT_FUTURE_BARS"] += 1
            continue

        outcome = label_decision(
            candles=candles,
            long_candidate=long_candidate,
            short_candidate=short_candidate,
            config=labeling_config,
        )

        # Defensive invariant: a complete-horizon decision should not
        # return the insufficient-future condition.
        if (
            outcome.long_outcome.outcome_reason
            == "INSUFFICIENT_FUTURE_BARS"
            or outcome.short_outcome.outcome_reason
            == "INSUFFICIENT_FUTURE_BARS"
        ):
            raise AssertionError(
                "Complete-horizon decision produced "
                "INSUFFICIENT_FUTURE_BARS"
            )

        outcomes.append(outcome)

    excluded = sum(exclusion_reasons.values())

    return (
        outcomes,
        excluded,
        tuple(exclusion_reasons.items()),
    )


def build_phase9_dataset(
    historical_dataset: HistoricalDataset,
    *,
    market_context: pd.DataFrame,
    sector_context: pd.DataFrame | None = None,
    sector_mappings: tuple[SectorMapping, ...] = (),
    indicator_engine: IndicatorEngine | None = None,
    candidate_config: CandidateConfig | None = None,
    labeling_config: LabelingConfig | None = None,
) -> Phase9DatasetResult:
    """
    Build a real Phase 9 TrainingDataset from historical market data.

    Parameters
    ----------
    historical_dataset:
        Validated canonical/research historical OHLCV dataset.

    market_context:
        Point-in-time market context required by the Phase 5 feature
        contract.

    sector_context:
        Optional point-in-time sector context.

    sector_mappings:
        Point-in-time sector mappings when sector context is supplied.

    indicator_engine:
        Phase 4 indicator engine. Defaults to the standard configuration.

    candidate_config:
        Causal structure + ATR candidate policy.

    labeling_config:
        Phase 7 outcome-labeling policy.

    Returns
    -------
    Phase9DatasetResult
        Auditable result containing the final TrainingDataset.
    """

    if not isinstance(
        historical_dataset,
        HistoricalDataset,
    ):
        raise TypeError(
            "historical_dataset must be a HistoricalDataset"
        )

    if not isinstance(market_context, pd.DataFrame):
        raise TypeError(
            "market_context must be a pandas DataFrame"
        )

    indicator_engine = (
        indicator_engine
        if indicator_engine is not None
        else IndicatorEngine()
    )

    candidate_config = (
        candidate_config
        if candidate_config is not None
        else CandidateConfig()
    )

    labeling_config = (
        labeling_config
        if labeling_config is not None
        else LabelingConfig()
    )

    candles = _candles_to_frame(historical_dataset)

    _validate_candle_frame(candles)

    # ---------------------------------------------------------------
    # Phase 4: indicators
    # ---------------------------------------------------------------
    indicators = indicator_engine.calculate(candles)

    # ---------------------------------------------------------------
    # Phase 5: causal ML features
    # ---------------------------------------------------------------
    features = build_features(
        indicators,
        market_context=market_context,
        sector_context=sector_context,
        sector_mappings=sector_mappings,
    )

    # ---------------------------------------------------------------
    # Phase 6: causal market regime
    # ---------------------------------------------------------------
    regime = detect_market_regime(features)

    # Regime is decision-time context. It is needed to establish
    # that the observation has a valid regime, but regime columns
    # are not part of the 40-feature ML matrix.
    #
    # Candidate construction must use the RAW INDICATOR layer,
    # because CandidateBuilder requires:
    #
    #     atr_{period}
    #     swing_high / swing_low
    #     support_{lookback}
    #     resistance_{lookback}
    #
    # These execution/structure inputs are intentionally not part
    # of FEATURE_COLUMNS.
    candidate_rows = indicators.merge(
        regime,
        on="timestamp",
        how="left",
        validate="many_to_one",
    )

    candidate_rows = candidate_rows.loc[
        candidate_rows["regime"].notna()
        & candidate_rows["regime_probability"].notna()
    ].copy()

    feature_rows = len(candidate_rows)

    if feature_rows == 0:
        raise ValueError(
            "no decision-time rows have a usable market regime"
        )

    # ---------------------------------------------------------------
    # Phase 7: both directional hypothetical outcomes
    # ---------------------------------------------------------------
    outcomes, excluded, exclusion_reasons = _build_labels(
    candles=candles,
    decision_rows=candidate_rows,
    candidate_config=candidate_config,
    labeling_config=labeling_config,
)

    if not outcomes:
        raise ValueError(
            "no eligible decision rows could produce Phase 7 labels"
        )

    # ---------------------------------------------------------------
    # Final supervised dataset
    #
    # Only timestamp/symbol + causal ML features + decision label
    # survive into TrainingDataset.
    # ---------------------------------------------------------------
    # Only feature observations that have a complete, valid decision
    # label may enter the supervised dataset.
    outcome_keys = pd.DataFrame(
        {
            "timestamp": [
                outcome.timestamp
                for outcome in outcomes
            ],
            "symbol": [
                outcome.symbol
                for outcome in outcomes
            ],
        }
    )

    eligible_features = features.merge(
        outcome_keys,
        on=["timestamp", "symbol"],
        how="inner",
        validate="one_to_one",
    )

    training_dataset = build_training_dataset(
        features=eligible_features,
        outcomes=outcomes,
    )

    # Preserve only decision-time inputs required to reproduce the frozen
    # Phase 8 BaselineStrategy benchmark. This stays outside
    # TrainingDataset so the ML feature contract remains unchanged.
    strategy_context = (
        candidate_rows.merge(
            outcome_keys,
            on=["timestamp", "symbol"],
            how="inner",
            validate="one_to_one",
        )
        .loc[
            :,
            [
                "timestamp",
                "symbol",
                "regime",
                "regime_probability",
                "vwap_distance_pct",
                "rvol_20",
                "higher_high",
                "higher_low",
                "lower_low",
                "lower_high",
            ],
        ]
        .sort_values(
            ["symbol", "timestamp"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    if len(strategy_context) != len(training_dataset.data):
        raise AssertionError(
            "Phase 9 strategy context must align one-to-one with "
            "the final TrainingDataset."
        )

    eligible_rows = len(outcomes)

    if eligible_rows + excluded != feature_rows:
        raise AssertionError(
            "Phase 9 eligibility accounting mismatch: "
            f"feature_rows={feature_rows}, "
            f"eligible_rows={eligible_rows}, "
            f"excluded_rows={excluded}"
        )

    return Phase9DatasetResult(
        training_dataset=training_dataset,
        feature_rows=feature_rows,
        eligible_rows=eligible_rows,
        excluded_rows=excluded,
        exclusion_reasons=exclusion_reasons,
        labels=tuple(outcomes),
        strategy_context=strategy_context,
    )