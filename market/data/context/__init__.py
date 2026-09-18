"""Point-in-time market and sector context for feature engineering."""

from market.data.context.alignment import align_context
from market.data.context.enrichment import (
    CONTEXT_FEATURE_COLUMNS,
    enrich_market_sector_context,
)
from market.data.context.market_context import build_context_returns
from market.data.context.models import SectorMapping
from market.data.context.sector_context import (
    build_sector_context,
    candles_to_context_frame,
)
from market.data.context.sector_mapping_io import load_sector_mappings_csv
from market.data.context.sector_registry import (
    DEFAULT_YFINANCE_INDEX_SYMBOLS,
    SECTOR_INDEX_SYMBOLS,
    provider_symbols_for,
)

__all__ = [
    "CONTEXT_FEATURE_COLUMNS",
    "SectorMapping",
    "align_context",
    "build_context_returns",
    "build_sector_context",
    "candles_to_context_frame",
    "DEFAULT_YFINANCE_INDEX_SYMBOLS",
    "SECTOR_INDEX_SYMBOLS",
    "provider_symbols_for",
    "load_sector_mappings_csv",
    "enrich_market_sector_context",
]
