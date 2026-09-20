"""Adapter from historical archive records to canonical ResearchDocument.

The adapter is intentionally mechanical: source-native causal timestamps and
content hashes are preserved. Archive provenance is carried in metadata.
"""
from __future__ import annotations

from datetime import datetime

from research.contracts import ResearchDocument
from research.corpus.archive import HistoricalArchiveRecord


def archive_record_to_document(
    record: HistoricalArchiveRecord,
    *,
    processed_at: datetime | None = None,
) -> ResearchDocument:
    """Convert one archive record without changing its PIT semantics.

    processed_at is non-causal pipeline provenance. When omitted, the archive
    timestamp is used; otherwise callers must supply a timezone-aware value
    that is not earlier than observed_at.
    """
    if processed_at is None:
        processed_at = record.archived_at or record.available_at
    if processed_at.tzinfo is None or processed_at.utcoffset() is None:
        raise ValueError("processed_at must be timezone-aware")
    if processed_at < record.observed_at:
        raise ValueError("processed_at cannot precede observed_at")

    metadata = dict(record.metadata)
    metadata["archive_id"] = record.archive_id
    metadata["archive_schema_version"] = record.schema_version
    metadata["source_reference"] = metadata.get(
        "source_reference",
        f"archive://{record.source_id}/{record.external_id}",
    )

    return ResearchDocument(
        document_id=record.archive_id,
        source_id=record.source_id,
        external_id=record.external_id,
        title=record.title,
        content=record.content,
        published_at=record.published_at,
        observed_at=record.observed_at,
        processed_at=processed_at,
        available_at=record.available_at,
        symbols=record.symbols,
        entities=record.entities,
        language=record.language,
        content_hash=record.content_hash,
        metadata=metadata,
    )