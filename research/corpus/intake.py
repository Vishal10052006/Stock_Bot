"""Reproducible NSE historical corpus intake and manifest generation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from research.corpus.archive import HistoricalArchiveRecord
from research.corpus.builder import HistoricalCorpusBuildAudit, HistoricalResearchCorpusBuilder
from research.corpus.nse_archive import NSEHistoricalArchiveClient, NSE_SOURCE_REFERENCE
from research.corpus.schema import HistoricalResearchCorpus, ResearchCorpusManifest


@dataclass(frozen=True, slots=True)
class HistoricalIntakeResult:
    corpus: HistoricalResearchCorpus
    audit: HistoricalCorpusBuildAudit
    raw_sha256: str
    archive_record_count: int


def ingest_nse_csv(
    csv_path: str | Path,
    *,
    archive_jsonl_path: str | Path,
    manifest_path: str | Path,
    dataset_id: str,
    version: str,
    accessed_at: datetime,
    archived_at: datetime,
    symbols: Sequence[str] = (),
    time_start: datetime | None = None,
    time_end: datetime | None = None,
) -> HistoricalIntakeResult:
    """Materialize an NSE archive into a reproducible PIT research corpus."""
    source = Path(csv_path)
    raw_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    parsed_records = NSEHistoricalArchiveClient.parse_csv(
        source,
        archived_at=archived_at,
    )
    records, duplicate_count = _deduplicate_archive_records(parsed_records)

    archive_path = Path(archive_jsonl_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(_archive_payload(record), sort_keys=True) + "\n"
            )

    manifest = ResearchCorpusManifest(
        dataset_id=dataset_id,
        version=version,
        source=NSE_SOURCE_REFERENCE,
        accessed_at=accessed_at,
        time_start=time_start,
        time_end=time_end,
        metadata={
            "raw_sha256": raw_sha256,
            "raw_archive_record_count": len(parsed_records),
            "deduplicated_archive_record_count": len(records),
            "exact_duplicate_archive_records": duplicate_count,
        },
    )
    corpus, audit = HistoricalResearchCorpusBuilder().build_from_archive_records(
        records,
        manifest=manifest,
        symbols=symbols,
        time_start=time_start,
        time_end=time_end,
    )

    output = {
        "schema_version": manifest.schema_version,
        "dataset_id": dataset_id,
        "version": version,
        "source": NSE_SOURCE_REFERENCE,
        "accessed_at": accessed_at.isoformat(),
        "time_start": corpus.time_start.isoformat() if corpus.time_start else None,
        "time_end": corpus.time_end.isoformat() if corpus.time_end else None,
        "document_count": corpus.document_count,
        "archive_record_count": len(records),
        "raw_archive_record_count": len(parsed_records),
        "exact_duplicate_archive_records": duplicate_count,
        "accepted_documents": audit.accepted_documents,
        "rejected_documents": audit.rejected_documents,
        "duplicate_documents": audit.duplicate_documents,
        "symbols": list(corpus.symbols),
        "raw_sha256": raw_sha256,
        "corpus_fingerprint": corpus.fingerprint,
    }
    manifest_file = Path(manifest_path)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return HistoricalIntakeResult(
        corpus=corpus,
        audit=audit,
        raw_sha256=raw_sha256,
        archive_record_count=len(records),
    )


def _deduplicate_archive_records(
    records: Sequence[HistoricalArchiveRecord],
) -> tuple[tuple[HistoricalArchiveRecord, ...], int]:
    """Collapse exact duplicate archive IDs and reject conflicting IDs.

    The raw NSE CSV remains the source of truth. Exact duplicate rows are a
    transport/intake duplication and are safely represented once in the
    canonical JSONL archive. A repeated archive_id with different payload is
    ambiguous and must fail rather than silently discarding evidence.
    """
    unique: dict[str, HistoricalArchiveRecord] = {}
    duplicate_count = 0

    for position, record in enumerate(records, start=1):
        previous = unique.get(record.archive_id)
        if previous is None:
            unique[record.archive_id] = record
            continue

        if _archive_payload(previous) != _archive_payload(record):
            raise ValueError(
                "conflicting archive_id during NSE intake at parsed record "
                f"{position}: {record.archive_id}"
            )

        duplicate_count += 1

    return tuple(unique.values()), duplicate_count


def _archive_payload(record: HistoricalArchiveRecord) -> dict:
    return {
        "archive_id": record.archive_id,
        "source_id": record.source_id,
        "external_id": record.external_id,
        "title": record.title,
        "content": record.content,
        "published_at": record.published_at.isoformat(),
        "observed_at": record.observed_at.isoformat(),
        "available_at": record.available_at.isoformat(),
        "symbols": list(record.symbols),
        "entities": list(record.entities),
        "language": record.language,
        "content_hash": record.content_hash,
        "metadata": dict(record.metadata),
        "archived_at": record.archived_at.isoformat() if record.archived_at else None,
        "schema_version": record.schema_version,
    }
