"""RB-4 point-in-time availability gate.

A document is eligible only when available_at <= decision_time.
"""
from __future__ import annotations
from datetime import datetime
from research.contracts import ResearchDocument


def is_available(document: ResearchDocument, decision_time: datetime) -> bool:
    return document.available_at <= decision_time


def filter_point_in_time(documents: tuple[ResearchDocument, ...] | list[ResearchDocument], decision_time: datetime) -> tuple[ResearchDocument, ...]:
    return tuple(d for d in documents if is_available(d, decision_time))
