"""Contracts for reproducible, point-in-time historical research corpora.

A corpus is an empirical input to the Research Bot. This module keeps the
contract separate from ingestion providers so a dataset can be validated
before it is used for historical experiments.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from research.contracts import ResearchDocument

CORPUS_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class ResearchCorpusManifest:
    """Reproducibility metadata for one historical corpus snapshot."""

    dataset_id: str
    version: str
    source: str
    accessed_at: datetime
    description: str = ""
    license: str | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None
    document_count: int | None = None
    schema_version: str = CORPUS_SCHEMA_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise ValueError("dataset_id must be non-empty")
        if not self.version.strip():
            raise ValueError("version must be non-empty")
        if not self.source.strip():
            raise ValueError("source must be non-empty")
        if not self.schema_version.strip():
            raise ValueError("schema_version must be non-empty")
        if self.time_start and self.time_end and self.time_end < self.time_start:
            raise ValueError("time_end cannot precede time_start")
        if self.document_count is not None and self.document_count < 0:
            raise ValueError("document_count cannot be negative")


@dataclass(frozen=True, slots=True)
class ResearchCorpusDocument:
    """A corpus document plus dataset-level provenance.

    ResearchDocument remains the canonical Research Bot document. This wrapper
    records which corpus snapshot supplied it and does not alter timestamps.
    """

    document: ResearchDocument
    dataset_id: str
    dataset_version: str
    source_reference: str

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise ValueError("dataset_id must be non-empty")
        if not self.dataset_version.strip():
            raise ValueError("dataset_version must be non-empty")
        if not self.source_reference.strip():
            raise ValueError("source_reference must be non-empty")


@dataclass(frozen=True, slots=True)
class HistoricalResearchCorpus:
    """Validated immutable snapshot of historical Research Bot documents."""

    manifest: ResearchCorpusManifest
    documents: tuple[ResearchCorpusDocument, ...]

    @classmethod
    def from_documents(
        cls,
        manifest: ResearchCorpusManifest,
        documents: Sequence[ResearchCorpusDocument],
    ) -> "HistoricalResearchCorpus":
        corpus = cls(manifest=manifest, documents=tuple(documents))
        corpus.validate()
        return corpus

    def validate(self) -> None:
        """Validate identity, chronology, and manifest/document consistency."""
        expected_dataset = self.manifest.dataset_id
        expected_version = self.manifest.version
        ids: set[str] = set()

        for item in self.documents:
            if item.dataset_id != expected_dataset:
                raise ValueError(
                    f"document {item.document.document_id!r} has dataset_id "
                    f"{item.dataset_id!r}, expected {expected_dataset!r}"
                )
            if item.dataset_version != expected_version:
                raise ValueError(
                    f"document {item.document.document_id!r} has dataset_version "
                    f"{item.dataset_version!r}, expected {expected_version!r}"
                )

            document = item.document
            if document.document_id in ids:
                raise ValueError(f"duplicate document_id: {document.document_id}")
            ids.add(document.document_id)

            if document.available_at < document.published_at:
                raise ValueError(
                    f"document {document.document_id!r} has available_at before published_at"
                )

            if self.manifest.time_start and document.published_at < self.manifest.time_start:
                raise ValueError(
                    f"document {document.document_id!r} precedes corpus time_start"
                )
            if self.manifest.time_end and document.published_at > self.manifest.time_end:
                raise ValueError(
                    f"document {document.document_id!r} exceeds corpus time_end"
                )

        if (
            self.manifest.document_count is not None
            and self.manifest.document_count != len(self.documents)
        ):
            raise ValueError(
                "manifest document_count does not match loaded document count"
            )

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    symbol
                    for item in self.documents
                    for symbol in item.document.symbols
                }
            )
        )

    @property
    def time_start(self) -> datetime | None:
        if not self.documents:
            return self.manifest.time_start
        return min(item.document.published_at for item in self.documents)

    @property
    def time_end(self) -> datetime | None:
        if not self.documents:
            return self.manifest.time_end
        return max(item.document.published_at for item in self.documents)

    @property
    def fingerprint(self) -> str:
        """Return a deterministic SHA-256 fingerprint of the corpus contents.

        The fingerprint is independent of document ordering and local storage
        paths. It includes the manifest identity and all ResearchDocument
        fields that affect historical research interpretation.
        """
        payload = {
            "schema_version": self.manifest.schema_version,
            "dataset_id": self.manifest.dataset_id,
            "dataset_version": self.manifest.version,
            "documents": [
                _document_fingerprint_payload(item.document)
                for item in sorted(
                    self.documents,
                    key=lambda item: item.document.document_id,
                )
            ],
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


def _document_fingerprint_payload(document: ResearchDocument) -> dict[str, Any]:
    """Build the stable, path-independent document fingerprint payload."""
    return {
        "document_id": document.document_id,
        "source_id": document.source_id,
        "external_id": document.external_id,
        "title": document.title,
        "content_hash": document.content_hash,
        "published_at": document.published_at.isoformat(),
        "observed_at": document.observed_at.isoformat(),
        "processed_at": document.processed_at.isoformat(),
        "available_at": document.available_at.isoformat(),
        "symbols": list(document.symbols),
        "entities": list(document.entities),
        "language": document.language,
    }
