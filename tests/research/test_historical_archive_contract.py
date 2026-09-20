from datetime import datetime, timezone
from hashlib import sha256

import pytest

from research.corpus.archive import HistoricalArchiveRecord


UTC = timezone.utc


def _record(**overrides) -> HistoricalArchiveRecord:
    values = {
        "archive_id": "archive-1",
        "source_id": "source-a",
        "external_id": "external-1",
        "title": "Historical filing",
        "content": "Revenue increased by 12%.",
        "published_at": datetime(2026, 1, 1, 10, tzinfo=UTC),
        "observed_at": datetime(2026, 1, 1, 10, 1, tzinfo=UTC),
        "available_at": datetime(2026, 1, 1, 10, 2, tzinfo=UTC),
        "archived_at": datetime(2026, 2, 1, tzinfo=UTC),
        "symbols": ("ABC",),
    }
    values.update(overrides)
    return HistoricalArchiveRecord(**values)


def test_archive_record_preserves_source_native_causal_timestamps():
    record = _record()

    assert record.published_at == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert record.observed_at == datetime(2026, 1, 1, 10, 1, tzinfo=UTC)
    assert record.available_at == datetime(2026, 1, 1, 10, 2, tzinfo=UTC)
    assert record.archived_at == datetime(2026, 2, 1, tzinfo=UTC)


def test_archive_record_computes_content_hash():
    record = _record()

    assert record.content_hash == sha256(record.content.encode("utf-8")).hexdigest()


def test_archive_record_rejects_incorrect_content_hash():
    with pytest.raises(ValueError, match="content_hash"):
        _record(content_hash="0" * 64)


def test_archive_record_rejects_non_causal_timestamp_order():
    with pytest.raises(ValueError, match="observed_at"):
        _record(observed_at=datetime(2026, 1, 1, 9, 59, tzinfo=UTC))


def test_archive_record_rejects_archive_before_source_availability():
    with pytest.raises(ValueError, match="archived_at"):
        _record(archived_at=datetime(2026, 1, 1, 10, 1, tzinfo=UTC))


def test_archive_record_rejects_timezone_naive_timestamp():
    with pytest.raises(ValueError, match="published_at"):
        _record(published_at=datetime(2026, 1, 1, 10))


def test_archive_record_has_stable_schema_version():
    assert _record().schema_version == "1.0"
