"""S08 timeframe recognition from structured OCR evidence."""

from __future__ import annotations

import re
from typing import Iterable

from .evidence import TimeframeEvidence
from .ocr import OCRToken


_PATTERN = re.compile(
    r"\b(1|3|5|15|30|45|60|120|240)\s*m(?:in)?\b|"
    r"\b(1|2|4|6|12|24)\s*h(?:our)?\b|"
    r"\b(1|2|3|5|10|15|30)\s*d(?:ay)?\b|"
    r"\b(1|2|3|4)\s*w(?:eek)?\b",
    re.IGNORECASE,
)


def normalize_timeframe(value: str) -> str | None:
    match = _PATTERN.search(value)
    if not match:
        return None
    if match.group(1):
        return f"{match.group(1)}m"
    if match.group(2):
        return f"{match.group(2)}h"
    if match.group(3):
        return f"{match.group(3)}D"
    if match.group(4):
        return f"{match.group(4)}W"
    return None


def detect_timeframe_evidence(
    tokens: Iterable[OCRToken],
) -> TimeframeEvidence | None:
    candidates: list[TimeframeEvidence] = []
    for token in tokens:
        normalized = normalize_timeframe(token.text)
        if normalized is not None:
            candidates.append(
                TimeframeEvidence(
                    value=normalized,
                    confidence=round(max(0.0, min(1.0, token.confidence / 100.0)), 4),
                    source="ocr",
                    bbox=token.bbox,
                )
            )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.confidence)
