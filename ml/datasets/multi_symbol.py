"""
Point-in-time aware multi-symbol Phase 9 dataset orchestration.

The existing Phase 9 pipeline intentionally operates on one
HistoricalDataset / instrument.  This module provides the outer
orchestration boundary:

PIT identity
    -> provider identity resolution
    -> one HistoricalDataRequest
    -> one HistoricalDataset
    -> existing build_phase9_dataset()
    -> per-symbol TrainingDataset
    -> global TrainingDataset
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Sequence

import pandas as pd

from market.data.historical.identity_resolution import (
    PointInTimeInstrumentResolver,
    ResolvedHistoricalInstrument,
)
from market.data.historical.models import (
    HistoricalDataRequest,
    HistoricalDataset,
)
from market.data.historical.pipeline import (
    HistoricalMarketDataPipeline,
)
from market.data.historical.point_in_time_universe import (
    UniverseIdentityRecord,
)
from ml.datasets.models import TrainingDataset
from ml.datasets.pipeline import (
    Phase9DatasetResult,
    build_phase9_dataset,
)
from ml.datasets.validation import validate_training_dataset


@dataclass(frozen=True, slots=True)
class MultiSymbolPhase9Failure:
    """Deterministic failure record for one PIT instrument."""

    symbol: str
    isin: str
    fin_instrm_id: str
    as_of: date
    stage: str
    error_type: str
    error_message: str


@dataclass(frozen=True, slots=True)
class MultiSymbolPhase9InstrumentResult:
    """Auditable result for one PIT instrument."""

    pit_identity: UniverseIdentityRecord
    resolved: ResolvedHistoricalInstrument
    historical_dataset: HistoricalDataset
    phase9_result: Phase9DatasetResult


@dataclass(frozen=True, slots=True)
class MultiSymbolPhase9Result:
    """Combined Phase 9 result across independently processed instruments."""

    training_dataset: TrainingDataset
    instruments: tuple[MultiSymbolPhase9InstrumentResult, ...]
    failures: tuple[MultiSymbolPhase9Failure, ...]
    feature_rows: int
    eligible_rows: int
    excluded_rows: int

    def __post_init__(self) -> None:
        if not isinstance(self.training_dataset, TrainingDataset):
            raise TypeError(
                "training_dataset must be a TrainingDataset"
            )

        if not isinstance(self.instruments, tuple):
            raise TypeError("instruments must be a tuple")

        if not isinstance(self.failures, tuple):
            raise TypeError("failures must be a tuple")

        for value_name in (
            "feature_rows",
            "eligible_rows",
            "excluded_rows",
        ):
            value = getattr(self, value_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"{value_name} must be a non-negative integer"
                )

        if self.feature_rows != self.eligible_rows + self.excluded_rows:
            raise ValueError(
                "feature_rows must equal eligible_rows + excluded_rows"
            )


def _empty_training_dataset(
    *,
    feature_columns: Sequence[str],
) -> TrainingDataset:
    """Construct an empty canonical TrainingDataset with the given schema."""

    return TrainingDataset(
        data=pd.DataFrame(
            columns=[
                "timestamp",
                "symbol",
                *feature_columns,
                "label",
            ]
        ),
        feature_columns=tuple(feature_columns),
    )


def _combine_training_datasets(
    datasets: Sequence[TrainingDataset],
) -> TrainingDataset:
    """Concatenate validated per-symbol datasets deterministically."""

    if not datasets:
        raise ValueError(
            "cannot construct a global TrainingDataset without successful "
            "instrument datasets"
        )

    feature_columns = tuple(datasets[0].feature_columns)

    for dataset in datasets:
        if tuple(dataset.feature_columns) != feature_columns:
            raise ValueError(
                "per-symbol TrainingDataset feature schemas do not match"
            )

    frames = [
        dataset.data.copy(deep=True)
        for dataset in datasets
    ]

    combined = pd.concat(
        frames,
        axis=0,
        ignore_index=True,
    )

    if combined.empty:
        raise ValueError(
            "successful instrument datasets produced no training rows"
        )

    combined["timestamp"] = pd.to_datetime(
        combined["timestamp"],
        utc=True,
    )

    combined = (
        combined
        .sort_values(
            ["symbol", "timestamp"],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )

    duplicate_count = int(
        combined[["timestamp", "symbol"]]
        .duplicated()
        .sum()
    )

    if duplicate_count:
        raise ValueError(
            "global TrainingDataset contains duplicate "
            f"(timestamp, symbol) rows: {duplicate_count}"
        )

    training = TrainingDataset(
        data=combined,
        feature_columns=feature_columns,
    )

    validate_training_dataset(training.data)

    return training


def build_multi_symbol_phase9_dataset(
    pit_identities: Sequence[UniverseIdentityRecord],
    *,
    as_of: date,
    historical_pipeline: HistoricalMarketDataPipeline,
    instrument_resolver: PointInTimeInstrumentResolver,
    market_context_provider: Callable[
        [HistoricalDataset],
        pd.DataFrame,
    ] | None = None,
    sector_context_provider: Callable[
        [HistoricalDataset],
        pd.DataFrame | None,
    ] | None = None,
    sector_mappings=(),
    start: datetime | None = None,
    end: datetime | None = None,
    feature_columns: Sequence[str] | None = None,
    continue_on_error: bool = True,
) -> MultiSymbolPhase9Result:
    """
    Build a point-in-time multi-symbol Phase 9 training dataset.

    Each PIT identity is resolved and ingested independently.  A failure
    for one instrument is recorded and does not mutate or contaminate
    another instrument's dataset.

    Context providers receive the resolved HistoricalDataset, which keeps
    market/sector context construction outside the identity layer.
    """

    if not isinstance(as_of, date):
        raise TypeError("as_of must be a date")

    if not isinstance(pit_identities, Sequence):
        raise TypeError("pit_identities must be a sequence")

    if not pit_identities:
        raise ValueError("pit_identities must not be empty")

    successful: list[MultiSymbolPhase9InstrumentResult] = []
    failures: list[MultiSymbolPhase9Failure] = []

    feature_row_total = 0
    eligible_row_total = 0
    excluded_row_total = 0

    for pit_identity in pit_identities:
        if not isinstance(pit_identity, UniverseIdentityRecord):
            raise TypeError(
                "pit_identities must contain UniverseIdentityRecord objects"
            )

        symbol = pit_identity.symbol.strip().upper()

        try:
            resolved = instrument_resolver.resolve(
                pit_identity,
                as_of=as_of,
            )
        except Exception as exc:
            failure = MultiSymbolPhase9Failure(
                symbol=symbol,
                isin=pit_identity.isin,
                fin_instrm_id=pit_identity.fin_instrm_id,
                as_of=as_of,
                stage="IDENTITY_RESOLUTION",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            failures.append(failure)

            if not continue_on_error:
                raise

            continue

        try:
            request = HistoricalDataRequest(
                symbol=resolved.provider_symbol,
                exchange="NSE",
                timeframe_minutes=5,
                start=start,
                end=end,
            )

            ingestion = historical_pipeline.ingest(request)
            historical_dataset = ingestion.dataset
        except Exception as exc:
            failure = MultiSymbolPhase9Failure(
                symbol=symbol,
                isin=pit_identity.isin,
                fin_instrm_id=pit_identity.fin_instrm_id,
                as_of=as_of,
                stage="HISTORICAL_INGESTION",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            failures.append(failure)

            if not continue_on_error:
                raise

            continue

        try:
            market_context = (
                market_context_provider(historical_dataset)
                if market_context_provider is not None
                else None
            )

            sector_context = (
                sector_context_provider(historical_dataset)
                if sector_context_provider is not None
                else None
            )

            phase9_result = build_phase9_dataset(
                historical_dataset,
                market_context=market_context,
                sector_context=sector_context,
                sector_mappings=sector_mappings,
            )
        except Exception as exc:
            failure = MultiSymbolPhase9Failure(
                symbol=symbol,
                isin=pit_identity.isin,
                fin_instrm_id=pit_identity.fin_instrm_id,
                as_of=as_of,
                stage="PHASE9_BUILD",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            failures.append(failure)

            if not continue_on_error:
                raise

            continue

        successful.append(
            MultiSymbolPhase9InstrumentResult(
                pit_identity=pit_identity,
                resolved=resolved,
                historical_dataset=historical_dataset,
                phase9_result=phase9_result,
            )
        )

        feature_row_total += phase9_result.feature_rows
        eligible_row_total += phase9_result.eligible_rows
        excluded_row_total += phase9_result.excluded_rows

    if not successful:
        raise ValueError(
            "multi-symbol Phase 9 produced no successful instrument "
            "datasets; inspect failures"
        )

    datasets = [
        result.phase9_result.training_dataset
        for result in successful
    ]

    training_dataset = _combine_training_datasets(datasets)

    if feature_columns is not None:
        requested_columns = tuple(feature_columns)
        if requested_columns != tuple(training_dataset.feature_columns):
            raise ValueError(
                "requested feature_columns do not match the canonical "
                "Phase 9 feature schema"
            )

    return MultiSymbolPhase9Result(
        training_dataset=training_dataset,
        instruments=tuple(successful),
        failures=tuple(failures),
        feature_rows=feature_row_total,
        eligible_rows=eligible_row_total,
        excluded_rows=excluded_row_total,
    )
