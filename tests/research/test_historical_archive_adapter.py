from datetime import datetime, timezone

import pytest

from research.corpus import HistoricalArchiveRecord
from research.corpus.adapter import archive_record_to_document

UTC = timezone.utc


def _record() -> HistoricalArchiveRecord:
    return HistoricalArchiveRecord(
        archive_id="archive-1",
        source_id="source-a",
        external_id="external-1",
        title="Historical filing",
        content="Revenue increased.",
        published_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        observed_at=datetime(2026, 1, 1, 10, 1, tzinfo=UTC),
        available_at=datetime(2026, 1, 1, 10, 2, tzinfo=UTC),
        symbols=("ABC",),
        archived_at=datetime(2026, 2, 1, tzinfo=UTC),
    )


def test_adapter_preserves_causal_timestamps_and_hash():
    record = _record()
    document = archive_record_to_document(record)

    assert document.document_id == record.archive_id
    assert document.external_id == record.external_id
    assert document.published_at == record.published_at
    assert document.observed_at == record.observed_at
    assert document.available_at == record.available_at
    assert document.content_hash == record.content_hash
    assert document.processed_at == record.archived_at


def test_adapter_preserves_archive_provenance():
    document = archive_record_to_document(_record())

    assert document.metadata["archive_id"] == "archive-1"
    assert document.metadata["archive_schema_version"] == "1.0"
    assert document.metadata["source_reference"] == "archive://source-a/external-1"


def test_adapter_accepts_explicit_processing_time():
    processing_time = datetime(2026, 2, 2, tzinfo=UTC)
    document = archive_record_to_document(_record(), processed_at=processing_time)

    assert document.processed_at == processing_time
    assert document.available_at == datetime(2026, 1, 1, 10, 2, tzinfo=UTC)


def test_adapter_rejects_processing_time_before_observation():
    with pytest.raises(ValueError, match="processed_at"):
        archive_record_to_document(
            _record(),
            processed_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        )


def test_adapter_rejects_naive_processing_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        archive_record_to_document(
            _record(),
            processed_at=datetime(2026, 2, 2),
        )