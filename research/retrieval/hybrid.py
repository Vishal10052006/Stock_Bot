"""Causal hybrid retrieval baseline with provenance."""
from __future__ import annotations
import re
from research.contracts import ResearchDocument
from research.retrieval.interface import ResearchRetriever, RetrievalHit


class HybridResearchRetriever(ResearchRetriever):
    def search(self, documents, query: str, *, as_of, top_k: int = 5):
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        hits = []
        for doc in documents:
            if doc.available_at > as_of:
                continue
            words = set(re.findall(r"[a-z0-9]+", f"{doc.title} {doc.content}".lower()))
            lexical = len(terms & words)
            recency_days = max(0.0, (as_of - doc.available_at).total_seconds() / 86400.0)
            score = lexical + 1.0 / (1.0 + recency_days)
            if lexical:
                hits.append(RetrievalHit(
                    document_id=doc.document_id,
                    score=score,
                    available_at=doc.available_at,
                    evidence=f"{doc.title}: {doc.content[:240]}",
                ))
        hits.sort(key=lambda hit: (hit.score, hit.available_at), reverse=True)
        return tuple(hits[:top_k])
