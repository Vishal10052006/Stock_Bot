"""Build reproducible historical Research Bot corpora from archived documents.

This layer accepts already-archived canonical ResearchDocument records. It does
not fetch live data and never replaces historical timestamps with ingestion
time. Documents that cannot satisfy the point-in-time contract are rejected
rather than repaired.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from research.contracts import ResearchDocument
from research.corpus.adapter import archive_record_to_document
from research.corpus.archive import HistoricalArchiveRecord
from research.corpus.schema import (
    HistoricalResearchCorpus,
    ResearchCorpusDocument,
    ResearchCorpusManifest,
)


@dataclass(frozen=True, slots=True)
class HistoricalCorpusBuildAudit:
    """Deterministic accounting for one historical corpus build."""

    input_documents: int
    accepted_documents: int
    duplicate_documents: int
    rejected_documents: int
    rejected_document_ids: tuple[str, ...]
    symbols_requested: tuple[str, ...]
    time_start: datetime | None
    time_end: datetime | None


class HistoricalResearchCorpusBuilder:
    """Build a PIT-valid corpus from archived ResearchDocument records."""

    def build_from_archive_records(
        self,
        records: Sequence[HistoricalArchiveRecord],
        *,
        manifest: ResearchCorpusManifest,
        symbols: Sequence[str] = (),
        time_start: datetime | None = None,
        time_end: datetime | None = None,
        require_point_in_time: bool = True,
        processed_at: datetime | None = None,
    ) -> tuple[HistoricalResearchCorpus, HistoricalCorpusBuildAudit]:
        """Adapt archived records, then build the normal validated corpus.

        The adapter preserves all causal source timestamps. processed_at only
        controls non-causal processing provenance on ResearchDocument.
        """
        documents = tuple(
            archive_record_to_document(record, processed_at=processed_at)
            for record in records
        )
        return self.build(
            documents,
            manifest=manifest,
            symbols=symbols,
            time_start=time_start,
            time_end=time_end,
            require_point_in_time=require_point_in_time,
        )
    def build(
        self,
        documents: Sequence[ResearchDocument],
        *,
        manifest: ResearchCorpusManifest,
        symbols: Sequence[str] = (),
        time_start: datetime | None = None,
        time_end: datetime | None = None,
        require_point_in_time: bool = True,
    ) -> tuple[HistoricalResearchCorpus, HistoricalCorpusBuildAudit]:
        if time_start and time_end and time_end < time_start:
            raise ValueError("time_end cannot precede time_start")

        requested_symbols = tuple(sorted({s.strip().upper() for s in symbols if s.strip()}))
        seen: set[str] = set()
        accepted: list[ResearchCorpusDocument] = []
        duplicate_count = 0
        rejected_ids: list[str] = []

        for document in documents:
            if document.document_id in seen:
                duplicate_count += 1
                continue
            seen.add(document.document_id)

            if requested_symbols and not set(document.symbols).intersection(requested_symbols):
                continue
            if time_start and document.published_at < time_start:
                continue
            if time_end and document.published_at > time_end:
                continue

            try:
                self._validate_document(
                    document,
                    require_point_in_time=require_point_in_time,
                )
            except ValueError:
                rejected_ids.append(document.document_id)
                continue

            source_reference = document.external_id
            if document.metadata:
                source_reference = str(
                    document.metadata.get("source_reference", source_reference)
                )

            accepted.append(
                ResearchCorpusDocument(
                    document=document,
                    dataset_id=manifest.dataset_id,
                    dataset_version=manifest.version,
                    source_reference=source_reference,
                )
            )

        final_manifest = ResearchCorpusManifest(
            dataset_id=manifest.dataset_id,
            version=manifest.version,
            source=manifest.source,
            accessed_at=manifest.accessed_at,
            description=manifest.description,
            license=manifest.license,
            time_start=manifest.time_start,
            time_end=manifest.time_end,
            document_count=len(accepted),
            schema_version=manifest.schema_version,
            metadata=manifest.metadata,
        )
        corpus = HistoricalResearchCorpus.from_documents(final_manifest, accepted)

        audit = HistoricalCorpusBuildAudit(
            input_documents=len(documents),
            accepted_documents=len(accepted),
            duplicate_documents=duplicate_count,
            rejected_documents=len(rejected_ids),
            rejected_document_ids=tuple(rejected_ids),
            symbols_requested=requested_symbols,
            time_start=time_start,
            time_end=time_end,
        )
        return corpus, audit

    @staticmethod
    def _validate_document(
        document: ResearchDocument,
        *,
        require_point_in_time: bool,
    ) -> None:
        timestamps = (
            document.published_at,
            document.observed_at,
            document.processed_at,
            document.available_at,
        )
        if any(
            timestamp.tzinfo is None or timestamp.utcoffset() is None
            for timestamp in timestamps
        ):
            raise ValueError(
                f"document {document.document_id!r} has timezone-naive timestamp"
            )
        if document.available_at < document.published_at:
            raise ValueError(
                f"document {document.document_id!r} has available_at before published_at"
            )
        if require_point_in_time and not document.available_at:
            raise ValueError(
                f"document {document.document_id!r} has no point-in-time availability"
            )
