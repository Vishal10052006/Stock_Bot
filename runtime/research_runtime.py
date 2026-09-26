"""M20.4 approved-source research orchestrator.

This layer composes the repository's existing research providers and causal
ResearchContextBuilder. It is evidence collection only: it never changes
Strategy, Risk, Safety, models, or execution state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from research.contracts import ResearchContext, ResearchDocument
from research.integration.context import ResearchContextBuilder
from research.providers.public_sources import pib_provider, rbi_provider


class ResearchProvider(Protocol):
    """Minimal provider contract used by the M20.4 orchestrator."""

    def fetch(
        self,
        *,
        symbols: tuple[str, ...] | list[str],
        start: datetime,
        end: datetime,
    ) -> tuple[ResearchDocument, ...]:
        ...


@dataclass(frozen=True, slots=True)
class ResearchEvidenceRun:
    """Auditable output of one approved-source collection run."""

    as_of: datetime
    symbols: tuple[str, ...]
    documents: tuple[ResearchDocument, ...]
    contexts: tuple[ResearchContext, ...]
    provider_ids: tuple[str, ...]

    def evidence(self) -> dict[str, object]:
        """Return compact, JSON-safe run evidence."""
        return {
            "as_of": self.as_of.isoformat(),
            "symbols": list(self.symbols),
            "provider_ids": list(self.provider_ids),
            "documents_collected": len(self.documents),
            "contexts_built": len(self.contexts),
            "point_in_time_context": True,
            "production_mutation": False,
            "live_broker_order_submission": False,
        }


class ApprovedResearchRuntime:
    """Collect attributable external evidence without trading authority."""

    def __init__(
        self,
        *,
        providers: tuple[ResearchProvider, ...] | None = None,
        context_builder: ResearchContextBuilder | None = None,
    ) -> None:
        self.providers = providers or (rbi_provider(), pib_provider())
        self.context_builder = context_builder or ResearchContextBuilder()

    def collect(
        self,
        *,
        symbols: tuple[str, ...] | list[str],
        start: datetime,
        end: datetime,
        as_of: datetime | None = None,
    ) -> ResearchEvidenceRun:
        """Fetch approved evidence and build point-in-time contexts."""
        normalized = tuple(
            sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()})
        )
        if not normalized:
            raise ValueError("at least one symbol is required")

        for value, name in ((start, "start"), (end, "end")):
            if value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if start > end:
            raise ValueError("start must not be after end")

        decision_time = as_of or end
        if decision_time.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if decision_time < start:
            raise ValueError("as_of must not be before start")

        documents: list[ResearchDocument] = []
        provider_ids: list[str] = []

        for provider in self.providers:
            source_id = str(getattr(provider, "source_id", provider.__class__.__name__))
            provider_ids.append(source_id)
            documents.extend(
                provider.fetch(
                    symbols=normalized,
                    start=start,
                    end=end,
                )
            )

        unique: dict[str, ResearchDocument] = {}
        for document in documents:
            unique[document.document_id] = document

        ordered_documents = tuple(
            sorted(
                unique.values(),
                key=lambda item: (
                    item.available_at,
                    item.published_at,
                    item.document_id,
                ),
            )
        )

        contexts = tuple(
            self.context_builder.build(
                symbol=symbol,
                as_of=decision_time,
                documents=ordered_documents,
            )
            for symbol in normalized
        )

        return ResearchEvidenceRun(
            as_of=decision_time,
            symbols=normalized,
            documents=ordered_documents,
            contexts=contexts,
            provider_ids=tuple(provider_ids),
        )
