"""Contract for source-native historical Research Bot archive records.

This layer is intentionally separate from ResearchDocument. An archive
record preserves what an external historical source supplied; a later adapter
may convert it into the canonical Research Bot document contract without
rewriting causal timestamps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping

HISTORICAL_ARCHIVE_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class HistoricalArchiveRecord:
    """Immutable source-native record used to reconstruct historical research.

    published_at, observed_at and available_at are causal source timestamps.
    They must never be replaced with ingestion/current time. archived_at is
    non-causal archive provenance and may be absent when the archive does not
    expose it.
    """

    archive_id: str
    source_id: str
    external_id: str
    title: str
    content: str
    published_at: datetime
    observed_at: datetime
    available_at: datetime
    symbols: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    language: str = "en"
    content_hash: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    archived_at: datetime | None = None
    schema_version: str = HISTORICAL_ARCHIVE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name in ("archive_id", "source_id", "external_id", "title", "content"):
            value = getattr(self, field_name)
            if not value.strip():
                raise ValueError(f"{field_name} must be non-empty")

        timestamps = (
            ("published_at", self.published_at),
            ("observed_at", self.observed_at),
            ("available_at", self.available_at),
        )
        for field_name, value in timestamps:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")

        if self.archived_at is not None and (
            self.archived_at.tzinfo is None or self.archived_at.utcoffset() is None
        ):
            raise ValueError("archived_at must be timezone-aware when provided")

        if self.observed_at < self.published_at:
            raise ValueError("observed_at cannot precede published_at")
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        if self.archived_at is not None and self.archived_at < self.available_at:
            raise ValueError("archived_at cannot precede available_at")

        expected_hash = sha256(self.content.encode("utf-8")).hexdigest()
        if self.content_hash and self.content_hash != expected_hash:
            raise ValueError("content_hash does not match content")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", expected_hash)

        if not self.schema_version.strip():
            raise ValueError("schema_version must be non-empty")
