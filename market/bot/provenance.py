"""Market Bot provenance helpers."""
from __future__ import annotations
from typing import Any

from .contracts import MarketContext


def build_provenance(context: MarketContext) -> dict[str, Any]:
    return {
        "market_version": context.metadata.market_version,
        "data_version": context.metadata.data_version,
        "feature_version": context.metadata.feature_version,
        "benchmark": context.benchmark,
        **dict(context.metadata.provenance),
    }
