"""S07 indicator recognition from structured OCR evidence."""

from __future__ import annotations

import re
from typing import Iterable

from .evidence import IndicatorEvidence
from .ocr import OCRToken
from .vision import INDICATORS


_ALIASES = {
    "BOLLINGER": ("BOLLINGER", "BB"),
    "SUPERTREND": ("SUPERTREND",),
}


def detect_indicator_evidence(
    tokens: Iterable[OCRToken],
) -> tuple[IndicatorEvidence, ...]:
    result: list[IndicatorEvidence] = []
    for token in tokens:
        text = token.text.upper()
        for indicator in INDICATORS:
            aliases = _ALIASES.get(indicator, (indicator,))
            match = next(
                (alias for alias in aliases if re.search(rf"\b{re.escape(alias)}\b", text)),
                None,
            )
            if match:
                confidence = max(0.0, min(1.0, token.confidence / 100.0))
                result.append(
                    IndicatorEvidence(
                        name=indicator,
                        confidence=round(confidence, 4),
                        source="ocr",
                        bbox=token.bbox,
                    )
                )
                break

    # Preserve first occurrence of each indicator; duplicate OCR tokens do not
    # inflate confidence or indicator count.
    unique: dict[str, IndicatorEvidence] = {}
    for item in result:
        if item.name not in unique or item.confidence > unique[item.name].confidence:
            unique[item.name] = item
    return tuple(unique.values())
