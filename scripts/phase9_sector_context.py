"""Build PIT sector-index context for one Phase 9 research date."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo
import os

import pandas as pd

from market.data.context import build_sector_context, load_sector_mappings_csv
from market.data.context.sector_membership import PointInTimeSectorMembershipProvider
from market.data.historical.adapters.upstox import UpstoxHistoricalMarketDataProvider
from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper

MAPPING_PATH = Path("data/reference/nse/sector_membership/sector_membership.csv")
IST = ZoneInfo("Asia/Kolkata")
SECTOR_INSTRUMENTS = {
    "NIFTY_IT": "NSE_INDEX|Nifty IT",
}


def build_phase9_sector_context_for_date(
    *,
    symbols: Sequence[str],
    as_of: date,
    lookback_days: int = 15,
    timeframe_minutes: int = 5,
    access_token: str | None = None,
) -> pd.DataFrame:
    """Fetch PIT-mapped sector indices using the canonical Upstox adapter."""
    if lookback_days <= 0:
        raise ValueError("lookback_days must be positive")

    access_token = (access_token or os.getenv("UPSTOX_ACCESS_TOKEN", "")).strip()
    if not access_token:
        raise ValueError("UPSTOX access_token is required")

    mappings = load_sector_mappings_csv(MAPPING_PATH)
    membership = PointInTimeSectorMembershipProvider(mappings)

    resolved = membership.resolve_many(
        symbols=symbols,
        as_of=as_of,
        require_complete=False,
    )

    sector_symbols = sorted(
        {
            resolution.sector_index_symbol
            for resolution in resolved
            if resolution.sector_index_symbol is not None
        }
    )

    if not sector_symbols:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "sector_index_symbol",
                "return_1",
                "return_3",
                "return_12",
                "volatility_20",
            ]
        )

    instrument_mapping = {
        symbol: SECTOR_INSTRUMENTS[symbol]
        for symbol in sector_symbols
        if symbol in SECTOR_INSTRUMENTS
    }
    if len(instrument_mapping) != len(sector_symbols):
        missing = sorted(set(sector_symbols).difference(instrument_mapping))
        raise ValueError(f"missing Upstox sector instrument mappings: {missing}")

    provider = UpstoxHistoricalMarketDataProvider(
        access_token=access_token,
        instrument_mapper=UpstoxInstrumentMapper(instrument_mapping),
    )

    start = datetime.combine(
        as_of - timedelta(days=lookback_days),
        time.min,
        tzinfo=IST,
    )
    end = datetime.combine(
        as_of + timedelta(days=1),
        time.min,
        tzinfo=IST,
    )

    return build_sector_context(
        provider,
        symbols=sector_symbols,
        timeframe_minutes=timeframe_minutes,
        start=start,
        end=end,
    )
