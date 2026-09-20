from __future__ import annotations

from datetime import date, datetime
from unittest.mock import Mock

import pandas as pd
import pytest

from market.data.historical.models import HistoricalDataRequest
from market.data.historical.point_in_time_universe import (
    UniverseIdentityRecord,
)
from ml.datasets.models import TrainingDataset
from ml.datasets.multi_symbol import (
    MultiSymbolPhase9Failure,
    build_multi_symbol_phase9_dataset,
)


def make_identity(symbol: str, isin: str) -> UniverseIdentityRecord:
    return UniverseIdentityRecord(
        symbol=symbol,
        isin=isin,
        fin_instrm_id=f"FID-{symbol}",
        upstox_instrument_key=f"NSE_EQ|{isin}",
    )


def make_training(symbol: str) -> TrainingDataset:
    from market.features.builder import FEATURE_COLUMNS

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=2,
        freq="5min",
        tz="Asia/Kolkata",
    )

    data = {
        "timestamp": timestamps,
        "symbol": [symbol, symbol],
    }

    boolean_columns = {
        "retest_up",
        "retest_down",
        "higher_high",
        "lower_low",
        "higher_low",
        "lower_high",
    }

    for index, column in enumerate(FEATURE_COLUMNS):
        if column in boolean_columns:
            data[column] = [False, True]
        else:
            data[column] = [float(index), float(index + 1)]

    data["label"] = ["LONG_SUCCESS", "NO_EDGE"]

    return TrainingDataset(
        data=pd.DataFrame(data),
        feature_columns=tuple(FEATURE_COLUMNS),
    )


def test_multi_symbol_combines_and_sorts_without_duplicate_identity() -> None:
    dataset_a = make_training("AAA")
    dataset_b = make_training("BBB")

    pipeline = Mock()
    resolver = Mock()

    class Result:
        pass

    phase9_a = Result()
    phase9_a.training_dataset = dataset_a
    phase9_a.feature_rows = 2
    phase9_a.eligible_rows = 2
    phase9_a.excluded_rows = 0

    phase9_b = Result()
    phase9_b.training_dataset = dataset_b
    phase9_b.feature_rows = 2
    phase9_b.eligible_rows = 2
    phase9_b.excluded_rows = 0

    resolver.resolve.side_effect = [
        Mock(provider_symbol="AAA"),
        Mock(provider_symbol="BBB"),
    ]

    historical_a = Mock(symbol="AAA")
    historical_b = Mock(symbol="BBB")

    pipeline.ingest.side_effect = [
        Mock(dataset=historical_a),
        Mock(dataset=historical_b),
    ]

    import ml.datasets.multi_symbol as module

    original = module.build_phase9_dataset
    module.build_phase9_dataset = Mock(
        side_effect=[phase9_a, phase9_b]
    )

    try:
        result = build_multi_symbol_phase9_dataset(
            [
                make_identity("AAA", "ISINA"),
                make_identity("BBB", "ISINB"),
            ],
            as_of=date(2026, 9, 1),
            historical_pipeline=pipeline,
            instrument_resolver=resolver,
            start=datetime.fromisoformat(
                "2026-09-01T09:15:00+05:30"
            ),
            end=datetime.fromisoformat(
                "2026-09-02T15:30:00+05:30"
            ),
        )
    finally:
        module.build_phase9_dataset = original

    assert isinstance(result.training_dataset, TrainingDataset)
    assert len(result.training_dataset.data) == 4
    assert result.failures == ()
    assert result.feature_rows == 4
    assert result.eligible_rows == 4
    assert result.excluded_rows == 0

    assert (
        result.training_dataset.data[
            ["timestamp", "symbol"]
        ].duplicated().sum()
        == 0
    )

    assert list(
        result.training_dataset.data["symbol"]
    ) == ["AAA", "AAA", "BBB", "BBB"]


def test_one_instrument_failure_is_recorded_and_other_survives() -> None:
    pipeline = Mock()
    resolver = Mock()

    resolver.resolve.side_effect = [
        RuntimeError("lineage unavailable"),
        Mock(provider_symbol="BBB"),
    ]

    pipeline.ingest.return_value = Mock(
        dataset=Mock(symbol="BBB")
    )

    phase9_result = Mock(
        training_dataset=make_training("BBB"),
        feature_rows=2,
        eligible_rows=2,
        excluded_rows=0,
    )

    import ml.datasets.multi_symbol as module

    original = module.build_phase9_dataset
    module.build_phase9_dataset = Mock(
        return_value=phase9_result
    )

    try:
        result = build_multi_symbol_phase9_dataset(
            [
                make_identity("AAA", "ISINA"),
                make_identity("BBB", "ISINB"),
            ],
            as_of=date(2026, 9, 1),
            historical_pipeline=pipeline,
            instrument_resolver=resolver,
        )
    finally:
        module.build_phase9_dataset = original

    assert len(result.instruments) == 1
    assert result.instruments[0].pit_identity.symbol == "BBB"

    assert len(result.failures) == 1
    failure = result.failures[0]

    assert isinstance(failure, MultiSymbolPhase9Failure)
    assert failure.symbol == "AAA"
    assert failure.stage == "IDENTITY_RESOLUTION"
    assert failure.error_type == "RuntimeError"
    assert failure.error_message == "lineage unavailable"


def test_historical_request_uses_resolved_provider_symbol() -> None:
    pipeline = Mock()
    resolver = Mock()

    resolver.resolve.return_value = Mock(
        provider_symbol="AEROPLANE",
    )

    pipeline.ingest.return_value = Mock(
        dataset=Mock(symbol="AEROPLANE")
    )

    phase9_result = Mock(
        training_dataset=make_training("AEROPLANE"),
        feature_rows=2,
        eligible_rows=2,
        excluded_rows=0,
    )

    import ml.datasets.multi_symbol as module

    original = module.build_phase9_dataset
    module.build_phase9_dataset = Mock(
        return_value=phase9_result
    )

    try:
        build_multi_symbol_phase9_dataset(
            [
                make_identity(
                    "AMIRCHAND",
                    "INE05TO01019",
                )
            ],
            as_of=date(2026, 7, 10),
            historical_pipeline=pipeline,
            instrument_resolver=resolver,
        )
    finally:
        module.build_phase9_dataset = original

    request = pipeline.ingest.call_args.args[0]

    assert isinstance(request, HistoricalDataRequest)
    assert request.symbol == "AEROPLANE"
    assert request.exchange == "NSE"
    assert request.timeframe_minutes == 5


def test_empty_successful_instrument_set_fails_closed() -> None:
    pipeline = Mock()
    resolver = Mock()
    resolver.resolve.side_effect = RuntimeError("failed")

    with pytest.raises(
        ValueError,
        match="no successful instrument datasets",
    ):
        build_multi_symbol_phase9_dataset(
            [make_identity("AAA", "ISINA")],
            as_of=date(2026, 9, 1),
            historical_pipeline=pipeline,
            instrument_resolver=resolver,
        )
