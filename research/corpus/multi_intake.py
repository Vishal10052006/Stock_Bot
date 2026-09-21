"""Reproducible multi-file historical Research corpus intake.

Combines independently downloaded source archives without rewriting their
historical timestamps. Each input file is fingerprinted individually and the
aggregate manifest is deterministic and path-independent.
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
from research.corpus.intake import _archive_payload
from research.corpus.nse_archive import NSEHistoricalArchiveClient, NSE_SOURCE_REFERENCE
from research.corpus.schema import HistoricalResearchCorpus, ResearchCorpusManifest

@dataclass(frozen=True, slots=True)
class CorpusInputFingerprint:
    sha256: str
    record_count: int

@dataclass(frozen=True, slots=True)
class MultiFileHistoricalIntakeResult:
    corpus: HistoricalResearchCorpus
    audit: HistoricalCorpusBuildAudit
    inputs: tuple[CorpusInputFingerprint, ...]
    archive_record_count: int
    raw_collection_sha256: str

def ingest_nse_csv_files(
    csv_paths: Sequence[str | Path],
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
) -> MultiFileHistoricalIntakeResult:
    """Combine NSE CSV snapshots into one deterministic PIT corpus."""
    paths = tuple(Path(path) for path in csv_paths)
    if not paths:
        raise ValueError("csv_paths must contain at least one file")

    records: list[HistoricalArchiveRecord] = []
    inputs: list[CorpusInputFingerprint] = []

    for path in paths:
        raw = path.read_bytes()
        parsed = NSEHistoricalArchiveClient.parse_csv(path, archived_at=archived_at)
        inputs.append(CorpusInputFingerprint(
            sha256=hashlib.sha256(raw).hexdigest(),
            record_count=len(parsed),
        ))
        records.extend(parsed)

    raw_collection_sha256 = hashlib.sha256(
        json.dumps([item.sha256 for item in inputs], separators=(",", ":")).encode()
    ).hexdigest()

    manifest = ResearchCorpusManifest(
        dataset_id=dataset_id,
        version=version,
        source=NSE_SOURCE_REFERENCE,
        accessed_at=accessed_at,
        time_start=time_start,
        time_end=time_end,
        metadata={
            "input_file_count": len(inputs),
            "raw_collection_sha256": raw_collection_sha256,
        },
    )

    corpus, audit = HistoricalResearchCorpusBuilder().build_from_archive_records(
        records,
        manifest=manifest,
        symbols=symbols,
        time_start=time_start,
        time_end=time_end,
    )

    unique_by_archive_id: dict[str, HistoricalArchiveRecord] = {}
    for record in records:
        unique_by_archive_id.setdefault(record.archive_id, record)

    archive_path = Path(archive_jsonl_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("w", encoding="utf-8") as handle:
        for record in sorted(unique_by_archive_id.values(), key=lambda item: item.archive_id):
            handle.write(json.dumps(_archive_payload(record), sort_keys=True) + "\n")

    manifest_payload = {
        "schema_version": manifest.schema_version,
        "dataset_id": dataset_id,
        "version": version,
        "source": NSE_SOURCE_REFERENCE,
        "accessed_at": accessed_at.isoformat(),
        "time_start": corpus.time_start.isoformat() if corpus.time_start else None,
        "time_end": corpus.time_end.isoformat() if corpus.time_end else None,
        "document_count": corpus.document_count,
        "archive_record_count": len(records),
        "accepted_documents": audit.accepted_documents,
        "rejected_documents": audit.rejected_documents,
        "duplicate_documents": audit.duplicate_documents,
        "symbols": list(corpus.symbols),
        "raw_collection_sha256": raw_collection_sha256,
        "inputs": [item.__dict__ if hasattr(item, "__dict__") else {
            "sha256": item.sha256, "record_count": item.record_count
        } for item in inputs],
        "corpus_fingerprint": corpus.fingerprint,
    }
    manifest_file = Path(manifest_path)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return MultiFileHistoricalIntakeResult(
        corpus=corpus,
        audit=audit,
        inputs=tuple(inputs),
        archive_record_count=len(records),
        raw_collection_sha256=raw_collection_sha256,
    )
