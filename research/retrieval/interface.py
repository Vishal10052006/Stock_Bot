"""Pluggable retrieval boundary for production RAG."""
from __future__ import annotations
from dataclasses import dataclass
from research.contracts import ResearchDocument


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    document_id: str
    score: float
    available_at: object
    evidence: str


class ResearchRetriever:
    def search(self, documents: tuple[ResearchDocument, ...], query: str, *, as_of, top_k: int = 5) -> tuple[RetrievalHit, ...]:
        raise NotImplementedError
