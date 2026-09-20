"""RB-1/RB-2 ingestion orchestration with no silent repair."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from research.contracts import ResearchDocument
from research.providers.base import ResearchProvider
from research.validation.documents import validate_documents


class ResearchIngestionPipeline:
    def __init__(self, provider: ResearchProvider) -> None:
        self.provider = provider

    def run(self, *, symbols: Sequence[str], start: datetime, end: datetime) -> tuple[ResearchDocument, ...]:
        documents = tuple(self.provider.fetch(symbols=symbols, start=start, end=end))
        validate_documents(documents)
        return documents
