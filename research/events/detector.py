"""RB-6 deterministic event detector; LLMs are not required for baseline operation."""
from __future__ import annotations
import re
from hashlib import sha256
from research.contracts import EventType, ResearchDocument, ResearchEvent

_RULES = (
    (EventType.EARNINGS, re.compile(r"\b(earnings|results|profit|revenue)\b", re.I)),
    (EventType.GUIDANCE, re.compile(r"\b(guidance|outlook|forecast)\b", re.I)),
    (EventType.CORPORATE_ACTION, re.compile(r"\b(dividend|buyback|split|merger|acquisition)\b", re.I)),
    (EventType.REGULATORY, re.compile(r"\b(regulator|sebi|approval|penalty|ban)\b", re.I)),
    (EventType.MACRO, re.compile(r"\b(inflation|repo rate|gdp|rbi|interest rate)\b", re.I)),
)


class EventDetector:
    def detect(self, document: ResearchDocument) -> tuple[ResearchEvent, ...]:
        text = f"{document.title} {document.content}"
        for event_type, pattern in _RULES:
            match = pattern.search(text)
            if match:
                event_id = sha256(f"{document.document_id}:{event_type.value}".encode()).hexdigest()[:24]
                return (ResearchEvent(
                    event_id=event_id,
                    document_id=document.document_id,
                    event_type=event_type,
                    symbol=document.symbols[0] if document.symbols else None,
                    event_time=document.published_at,
                    available_at=document.available_at,
                    importance=0.5,
                    confidence=0.6,
                    evidence=match.group(0),
                ),)
        return ()
