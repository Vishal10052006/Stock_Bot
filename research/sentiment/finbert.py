"""Optional FinBERT sentiment adapter for Research Bot.

The adapter is intentionally dependency-light at import time: transformers and
torch are imported only when a live model instance is created. This keeps the
core test suite deterministic and avoids silently downloading model weights.

Default model: ProsusAI/finbert.
The caller must explicitly provide the model identifier and environment needed
for inference.
"""

from __future__ import annotations

from typing import Any

from research.contracts import ResearchDocument, SentimentResult


class FinBertSentiment:
    """Financial sentiment adapter backed by a Hugging Face text classifier."""

    def __init__(
        self,
        *,
        model_name: str = "ProsusAI/finbert",
        classifier: Any | None = None,
        device: int | str | None = None,
    ) -> None:
        self.model_version = f"finbert:{model_name}"
        if classifier is not None:
            self._classifier = classifier
            return

        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError(
                "FinBertSentiment requires the optional 'transformers' package. "
                "Install the research NLP dependencies before enabling it."
            ) from exc

        kwargs = {
            "task": "text-classification",
            "model": model_name,
            "tokenizer": model_name,
        }
        if device is not None:
            kwargs["device"] = device

        self._classifier = pipeline(**kwargs)

    def analyze(self, document: ResearchDocument) -> SentimentResult:
        text = f"{document.title}\n{document.content}".strip()
        scores = self._predict_scores(text)

        positive = scores.get("positive", 0.0)
        negative = scores.get("negative", 0.0)
        neutral = scores.get("neutral", 0.0)

        label = max(
            ("positive", positive),
            ("negative", negative),
            ("neutral", neutral),
            key=lambda item: item[1],
        )[0]

        # Signed sentiment is separated from confidence:
        # positive probability minus negative probability.
        score = max(-1.0, min(1.0, positive - negative))
        confidence = max(positive, negative, neutral)

        return SentimentResult(
            label=label,
            score=score,
            confidence=confidence,
            model_version=self.model_version,
        )

    def _predict_scores(self, text: str) -> dict[str, float]:
        try:
            raw = self._classifier(
                text,
                truncation=True,
                max_length=512,
                top_k=None,
            )
        except TypeError:
            # Compatibility with older transformers pipeline APIs.
            raw = self._classifier(
                text,
                truncation=True,
                max_length=512,
                return_all_scores=True,
            )

        # Normalise the common pipeline shapes:
        # [{"label": "...", "score": ...}, ...]
        # [[{"label": "...", "score": ...}, ...]]
        if raw and isinstance(raw[0], list):
            raw = raw[0]

        scores: dict[str, float] = {}
        for item in raw or ():
            label = str(item["label"]).strip().lower()
            scores[label] = float(item["score"])

        required = {"positive", "negative", "neutral"}
        missing = required - scores.keys()
        if missing:
            raise ValueError(
                f"FinBERT classifier did not return required labels: {sorted(missing)}"
            )
        return scores
