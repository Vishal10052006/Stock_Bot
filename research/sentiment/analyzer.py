"""RB-7 transparent lexicon baseline; replaceable by a validated model later."""
from __future__ import annotations
import re
from research.contracts import ResearchDocument, SentimentResult

_POSITIVE = {"growth", "strong", "positive", "beat", "profit", "upgrade", "improve", "record"}
_NEGATIVE = {"loss", "weak", "negative", "miss", "downgrade", "decline", "penalty", "risk"}


class LexiconSentiment:
    model_version = "lexicon-1.0"

    def analyze(self, document: ResearchDocument) -> SentimentResult:
        words = re.findall(r"[a-z]+", document.content.lower())
        pos = sum(w in _POSITIVE for w in words)
        neg = sum(w in _NEGATIVE for w in words)
        total = pos + neg
        score = 0.0 if total == 0 else (pos - neg) / total
        label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
        confidence = min(1.0, total / 10.0)
        return SentimentResult(label, score, confidence, self.model_version)
