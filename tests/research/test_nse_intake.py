from datetime import datetime, timezone

import pytest

from research.corpus.archive import HistoricalArchiveRecord
from research.corpus.intake import _deduplicate_archive_records

UTC = timezone.utc


def _record(*, archive_id="a1", content="Revenue increased."):
    return HistoricalArchiveRecord(
        archive_id=archive_id,
        source_id="nse-corporate-filings",
        external_id="x1",
        title="Historical event",
        content=content,
        published_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        observed_at=datetime(2026, 1, 1, 10, 1, tzinfo=UTC),
        available_at=datetime(2026, 1, 1, 10, 2, tzinfo=UTC),
        symbols=("ABC",),
        metadata={"source_reference": "https://example.test"},
        archived_at=datetime(2026, 2, 1, tzinfo=UTC),
    )


def test_exact_duplicate_archive_records_are_collapsed():
    record = _record()

    records, duplicate_count = _deduplicate_archive_records(
        (record, record)
    )

    assert records == (record,)
    assert duplicate_count == 1


def test_conflicting_duplicate_archive_ids_are_rejected():
    first = _record(content="Revenue increased.")
    second = _record(content="Revenue decreased.")

    with pytest.raises(ValueError, match="conflicting archive_id"):
        _deduplicate_archive_records((first, second))


def test_distinct_archive_ids_are_preserved():
    first = _record(archive_id="a1")
    second = _record(archive_id="a2")

    records, duplicate_count = _deduplicate_archive_records(
        (first, second)
    )

    assert records == (first, second)
    assert duplicate_count == 0
