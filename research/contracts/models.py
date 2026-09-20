"""Canonical Research Bot contracts.

References:
    STOCK_BOT Research Bot roadmap: RB-0 through RB-14.
    STOCK_BOT Trading Specification: causality/provenance requirements.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping


class EventType(str, Enum):
    NEWS = "NEWS"
    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    REGULATORY = "REGULATORY"
    MACRO = "MACRO"
    SECTOR = "SECTOR"
    MANAGEMENT = "MANAGEMENT"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class ResearchSource:
    source_id: str
    provider_name: str
    source_type: str
    reliability: float = 0.5
    active: bool = True


@dataclass(frozen=True, slots=True)
class ResearchDocument:
    document_id: str
    source_id: str
    external_id: str
    title: str
    content: str
    published_at: datetime
    observed_at: datetime
    processed_at: datetime
    available_at: datetime
    symbols: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    language: str = "en"
    content_hash: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.observed_at < self.published_at:
            # Observation can occur after publication, but not before it.
            raise ValueError("observed_at cannot precede published_at")
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        if self.processed_at < self.observed_at:
            raise ValueError("processed_at cannot precede observed_at")
        if not self.content_hash:
            object.__setattr__(
                self,
                "content_hash",
                sha256(self.content.encode("utf-8")).hexdigest(),
            )


@dataclass(frozen=True, slots=True)
class ResearchEvent:
    event_id: str
    document_id: str
    event_type: EventType
    symbol: str | None
    event_time: datetime
    available_at: datetime
    importance: float
    confidence: float
    evidence: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SentimentResult:
    label: str
    score: float
    confidence: float
    model_version: str


@dataclass(frozen=True, slots=True)
class ImpactResult:
    company: float | None
    sector: float | None
    market: float | None
    horizon: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ResearchContext:
    symbol: str
    as_of: datetime
    documents: tuple[ResearchDocument, ...]
    events: tuple[ResearchEvent, ...]
    sentiment: tuple[SentimentResult, ...]
    impacts: tuple[ImpactResult, ...]
    provenance: tuple[str, ...]
    research_version: str = "RB-14.0"

    @property
    def source_count(self) -> int:
        return len({d.source_id for d in self.documents})
