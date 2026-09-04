"""Tests for deterministic historical dataset storage."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from market.candles.models import Candle
from market.data.historical.corporate_actions import (
    CorporateAction,
    CorporateActionType,
)
from market.data.historical.models import HistoricalDataset
from market.data.historical.storage import (
    HistoricalDatasetStore,
    JsonHistoricalDatasetStore,
)


IST = ZoneInfo("Asia/Kolkata")


def make_dataset() -> HistoricalDataset:
    return HistoricalDataset(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        bars=(
            Candle(
                symbol="RELIANCE",
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=datetime(
                    2026,
                    8,
                    27,
                    9,
                    15,
                    tzinfo=IST,
                ),
                open=2500.0,
                high=2520.0,
                low=2490.0,
                close=2510.0,
                volume=100000.0,
            ),
            Candle(
                symbol="RELIANCE",
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=datetime(
                    2026,
                    8,
                    27,
                    9,
                    20,
                    tzinfo=IST,
                ),
                open=2510.0,
                high=2530.0,
                low=2500.0,
                close=2525.0,
                volume=110000.0,
            ),
        ),
        metadata={
            "provider": "upstox",
            "instrument_key": "NSE_EQ|INE002A01018",
            "source_version": "test-v1",
        },
    )


def test_json_store_implements_storage_contract():
    store = JsonHistoricalDatasetStore()

    assert isinstance(store, HistoricalDatasetStore)


def test_round_trip_preserves_dataset(tmp_path: Path):
    dataset = make_dataset()
    store = JsonHistoricalDatasetStore()

    path = tmp_path / "historical.json"

    store.save(dataset, path)
    restored = store.load(path)

    assert restored == dataset


def test_round_trip_preserves_corporate_actions(tmp_path: Path):
    dataset = make_dataset()
    action = CorporateAction(
        isin="INE002A01018",
        action_type=CorporateActionType.DIVIDEND,
        ex_date=date(2026, 8, 28),
        announcement_date=date(2026, 8, 20),
        record_date=date(2026, 8, 29),
        amount=Decimal("12.345678901234567890"),
        currency="INR",
        source="test-source",
    )

    dataset = HistoricalDataset(
        symbol=dataset.symbol,
        exchange=dataset.exchange,
        timeframe_minutes=dataset.timeframe_minutes,
        bars=dataset.bars,
        metadata=dataset.metadata,
        corporate_actions=(action,),
    )

    store = JsonHistoricalDatasetStore()
    path = tmp_path / "historical.json"

    store.save(dataset, path)
    restored = store.load(path)

    assert restored.corporate_actions == (action,)
    assert restored.corporate_actions[0].action_type is CorporateActionType.DIVIDEND
    assert restored.corporate_actions[0].amount == Decimal(
        "12.345678901234567890"
    )


def test_round_trip_preserves_timezone(tmp_path: Path):
    dataset = make_dataset()
    store = JsonHistoricalDatasetStore()

    path = tmp_path / "historical.json"

    store.save(dataset, path)
    restored = store.load(path)

    assert restored.bars[0].timestamp.tzinfo is not None
    assert restored.bars[0].timestamp == dataset.bars[0].timestamp


def test_round_trip_preserves_exchange_and_timeframe(
    tmp_path: Path,
):
    dataset = make_dataset()
    store = JsonHistoricalDatasetStore()

    path = tmp_path / "historical.json"

    store.save(dataset, path)
    restored = store.load(path)

    assert restored.exchange == "NSE"
    assert restored.timeframe_minutes == 5
    assert restored.bars[0].exchange == "NSE"
    assert restored.bars[0].timeframe_minutes == 5


def test_save_is_deterministic(tmp_path: Path):
    dataset = make_dataset()
    store = JsonHistoricalDatasetStore()

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    store.save(dataset, first)
    store.save(dataset, second)

    assert first.read_bytes() == second.read_bytes()


def test_schema_version_is_written(tmp_path: Path):
    dataset = make_dataset()
    store = JsonHistoricalDatasetStore()

    path = tmp_path / "historical.json"

    store.save(dataset, path)

    payload = path.read_text(encoding="utf-8")

    assert '"schema_version": "2"' in payload


def test_metadata_is_deterministically_sorted(tmp_path: Path):
    dataset = HistoricalDataset(
        symbol=make_dataset().symbol,
        exchange="NSE",
        timeframe_minutes=5,
        bars=make_dataset().bars,
        metadata={
            "z": "last",
            "a": "first",
        },
    )

    store = JsonHistoricalDatasetStore()
    path = tmp_path / "historical.json"

    store.save(dataset, path)

    text = path.read_text(encoding="utf-8")

    assert text.index('"a": "first"') < text.index('"z": "last"')


def test_unsupported_schema_is_rejected(tmp_path: Path):
    path = tmp_path / "invalid.json"

    path.write_text(
        '{"schema_version": "999"}\n',
        encoding="utf-8",
    )

    store = JsonHistoricalDatasetStore()

    with pytest.raises(
        ValueError,
        match="unsupported historical dataset schema version",
    ):
        store.load(path)


def test_schema_one_artifact_remains_loadable(tmp_path: Path):
    path = tmp_path / "schema-one.json"

    path.write_text(
        '''
{
  "schema_version": "1",
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "timeframe_minutes": 5,
  "metadata": {
    "provider": "legacy"
  },
  "bars": [
    {
      "symbol": "RELIANCE",
      "exchange": "NSE",
      "timeframe_minutes": 5,
      "timestamp": "2026-08-27T09:15:00+05:30",
      "open": 2500.0,
      "high": 2520.0,
      "low": 2490.0,
      "close": 2510.0,
      "volume": 100000.0
    }
  ]
}
'''.strip(),
        encoding="utf-8",
    )

    store = JsonHistoricalDatasetStore()
    restored = store.load(path)

    assert restored.symbol == "RELIANCE"
    assert restored.exchange == "NSE"
    assert restored.timeframe_minutes == 5
    assert len(restored.bars) == 1
    assert restored.metadata["provider"] == "legacy"
    assert restored.corporate_actions == ()


def test_malformed_json_is_rejected(tmp_path: Path):
    path = tmp_path / "invalid.json"

    path.write_text(
        "{not valid json",
        encoding="utf-8",
    )

    store = JsonHistoricalDatasetStore()

    with pytest.raises(
        ValueError,
        match="unable to read historical dataset artifact",
    ):
        store.load(path)


def test_missing_required_field_is_rejected(tmp_path: Path):
    path = tmp_path / "invalid.json"

    path.write_text(
        '{"schema_version": "1", "symbol": "RELIANCE"}\n',
        encoding="utf-8",
    )

    store = JsonHistoricalDatasetStore()

    with pytest.raises(
        ValueError,
        match="missing fields",
    ):
        store.load(path)


def test_invalid_bar_is_rejected(tmp_path: Path):
    path = tmp_path / "invalid.json"

    path.write_text(
        """
{
  "schema_version": "1",
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "timeframe_minutes": 5,
  "metadata": {},
  "bars": [
    {
      "symbol": "RELIANCE",
      "exchange": "NSE",
      "timeframe_minutes": 5,
      "timestamp": "not-a-timestamp",
      "open": 100,
      "high": 105,
      "low": 95,
      "close": 102,
      "volume": 1000
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    store = JsonHistoricalDatasetStore()

    with pytest.raises(
        ValueError,
        match="invalid historical dataset bar",
    ):
        store.load(path)


def test_save_rejects_non_dataset(tmp_path: Path):
    store = JsonHistoricalDatasetStore()

    with pytest.raises(
        TypeError,
        match="HistoricalDataset",
    ):
        store.save(
            [],
            tmp_path / "invalid.json",
        )


def test_load_missing_file_is_rejected(tmp_path: Path):
    store = JsonHistoricalDatasetStore()

    with pytest.raises(FileNotFoundError):
        store.load(tmp_path / "missing.json")


def test_save_rejects_directory(tmp_path: Path):
    dataset = make_dataset()
    destination = tmp_path / "dataset"
    destination.mkdir()

    store = JsonHistoricalDatasetStore()

    with pytest.raises(
        ValueError,
        match="must be a file",
    ):
        store.save(dataset, destination)
