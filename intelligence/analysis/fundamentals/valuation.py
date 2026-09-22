"""Valuation interpretation kept separate from financial-statement facts."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from intelligence.analysis.fundamentals.contracts import ValuationSnapshot


def analyze_valuation(snapshot: ValuationSnapshot | None) -> dict[str, Any]:
    """Return market-derived valuation facts without producing a trade signal."""
    if snapshot is None:
        return {"available": False, "ratios": {}, "source": None}
    if isinstance(snapshot, Mapping):
        return {
            "available": bool(snapshot.get("available", True)),
            "as_of": snapshot.get("as_of"),
            "price": snapshot.get("price"),
            "ratios": dict(snapshot.get("ratios", {})),
            "source": snapshot.get("source"),
            "source_version": snapshot.get("source_version"),
        }
    return {
        "available": True,
        "as_of": snapshot.as_of.isoformat(),
        "price": snapshot.price,
        "ratios": snapshot.ratios(),
        "source": snapshot.source,
        "source_version": snapshot.source_version,
    }
