"""RB-10 dependency-light retrieval baseline; vector RAG remains replaceable."""
from __future__ import annotations
import re
from research.contracts import ResearchDocument


class LexicalResearchRetriever:
    def search(self, documents: tuple[ResearchDocument, ...], query: str, top_k: int = 5) -> tuple[ResearchDocument, ...]:
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        scored = []
        for doc in documents:
            words = set(re.findall(r"[a-z0-9]+", f"{doc.title} {doc.content}".lower()))
            score = len(terms & words)
            if score:
                scored.append((score, doc.available_at, doc))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return tuple(doc for _, _, doc in scored[:top_k])
