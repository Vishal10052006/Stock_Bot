"""RB-5 deterministic document normalization."""
from __future__ import annotations

import re
from dataclasses import replace
from research.contracts import ResearchDocument


class DocumentNormalizer:
    def normalize(self, document: ResearchDocument) -> ResearchDocument:
        title = re.sub(r"\s+", " ", document.title).strip()
        content = re.sub(r"\s+", " ", document.content).strip()
        return replace(document, title=title, content=content)
