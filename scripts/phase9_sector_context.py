"""Build PIT sector-index context for one Phase 9 research date."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo
<<<<<<< HEAD
import os

import pandas as pd

from market.data.context import build_sector_context, load_sector_mappings_csv
from market.data.context.sector_membership import PointInTimeSectorMembershipProvider
from market.data.historical.adapters.upstox import UpstoxHistoricalMarketDataProvider
from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper
=======

import pandas as pd

from market.data.context import (
    build_sector_context,
    load_sector_mappings_csv,
)
from market.data.context.sector_membership import (
    PointInTimeSectorMembershipProvider,
)
from market.data.historical.adapters.upstox import (
    UpstoxHistoricalMarketDataProvider,
)
from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)
from market.data.context.sector_registry import (
    DEFAULT_UPSTOX_INDEX_INSTRUMENT_KEYS,
)
>>>>>>> 9c8dc74 (fix(prediction): use canonical Upstox sector history)

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
<<<<<<< HEAD
    """Fetch PIT-mapped sector indices using the canonical Upstox adapter."""
=======
    """Fetch only PIT-mapped sector indices for one research date.

    Upstox is the canonical historical provider. Sector membership remains
    point-in-time; unsupported provider mappings remain absent rather than
    being fabricated.
    """
>>>>>>> 9c8dc74 (fix(prediction): use canonical Upstox sector history)
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

<<<<<<< HEAD
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
=======
    token = access_token
    if token is None:
        import os

        token = os.getenv("UPSTOX_ACCESS_TOKEN")

    if not token or not token.strip():
        raise ValueError(
            "access_token or UPSTOX_ACCESS_TOKEN is required for sector context"
        )

    supported = [
        symbol
        for symbol in sector_symbols
        if symbol in DEFAULT_UPSTOX_INDEX_INSTRUMENT_KEYS
    ]
    if not supported:
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

    instrument_mapper = UpstoxInstrumentMapper(
        {
            symbol: DEFAULT_UPSTOX_INDEX_INSTRUMENT_KEYS[symbol]
            for symbol in supported
        }
    )
    provider = UpstoxHistoricalMarketDataProvider(
        access_token=token,
        instrument_mapper=instrument_mapper,
>>>>>>> 9c8dc74 (fix(prediction): use canonical Upstox sector history)
    )

    ist = ZoneInfo("Asia/Kolkata")
    start = datetime.combine(
        as_of - timedelta(days=lookback_days),
        time.min,
<<<<<<< HEAD
        tzinfo=IST,
=======
        tzinfo=ist,
>>>>>>> 9c8dc74 (fix(prediction): use canonical Upstox sector history)
    )
    end = datetime.combine(
        as_of + timedelta(days=1),
        time.min,
<<<<<<< HEAD
        tzinfo=IST,
=======
        tzinfo=ist,
>>>>>>> 9c8dc74 (fix(prediction): use canonical Upstox sector history)
    )

    return build_sector_context(
        provider,
        symbols=supported,
        timeframe_minutes=timeframe_minutes,
        start=start,
        end=end,
    )
