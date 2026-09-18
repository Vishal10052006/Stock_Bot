"""Real-market smoke test for the Phase 9 dataset pipeline."""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from market.data.context import SectorMapping, build_context_returns
from market.data.historical.adapters import (
    YFinanceHistoricalIndexMarketDataProvider,
    YFinanceHistoricalMarketDataProvider,
)
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.pipeline import HistoricalMarketDataPipeline
from ml.datasets.pipeline import build_phase9_dataset


def candles_to_frame(bars) -> pd.DataFrame:
    """Convert canonical candles to an OHLCV DataFrame."""
    return pd.DataFrame(
        [
            {
                "timestamp": bar.timestamp,
                "symbol": bar.symbol,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]
    )


print("=" * 72)
print("PHASE 9 — REAL MARKET DATA SMOKE TEST")
print("=" * 72)

# ---------------------------------------------------------------------
# 1. RELIANCE
# ---------------------------------------------------------------------

print("\n[1] Downloading RELIANCE 5-minute data...")

equity_provider = YFinanceHistoricalMarketDataProvider(
    period="5d",
    auto_adjust=False,
)

equity_pipeline = HistoricalMarketDataPipeline(
    equity_provider,
    require_complete_sessions=False,
)

request = HistoricalDataRequest(
    symbol="RELIANCE",
    exchange="NSE",
    timeframe_minutes=5,
)

historical = equity_pipeline.ingest(request)

historical_dataset = historical.dataset

print("    Symbol:", historical_dataset.symbol)
print("    Timeframe:", historical_dataset.timeframe_minutes)
print("    Bars:", len(historical_dataset.bars))
print("    First bar:", historical_dataset.bars[0].timestamp)
print("    Last bar:", historical_dataset.bars[-1].timestamp)


# ---------------------------------------------------------------------
# 2. NIFTY 50 MARKET CONTEXT
# ---------------------------------------------------------------------

print("\n[2] Downloading NIFTY 50 market context...")

nifty = yf.Ticker("^NSEI").history(
    period="5d",
    interval="5m",
    auto_adjust=False,
)

if nifty.empty:
    raise RuntimeError("NIFTY 50 returned no data")

nifty = nifty.reset_index()

nifty_timestamps = pd.to_datetime(nifty["Datetime"])

if nifty_timestamps.dt.tz is None:
    nifty_timestamps = nifty_timestamps.dt.tz_localize("UTC")

nifty_timestamps = nifty_timestamps.dt.tz_convert("Asia/Kolkata")

market_raw = pd.DataFrame(
    {
        "timestamp": nifty_timestamps,
        "close": pd.to_numeric(nifty["Close"], errors="raise"),
    }
)

market_context = build_context_returns(market_raw)

print("    Context rows:", len(market_context))
print("    First:", market_context["timestamp"].min())
print("    Last:", market_context["timestamp"].max())


# ---------------------------------------------------------------------
# 3. NIFTY OIL & GAS SECTOR CONTEXT
# ---------------------------------------------------------------------

print("\n[3] Downloading NIFTY Oil & Gas sector context...")

sector_provider = YFinanceHistoricalIndexMarketDataProvider(
    period="5d",
    auto_adjust=False,
)

sector_request = HistoricalDataRequest(
    symbol="NIFTY_OIL_AND_GAS",
    exchange="NSE",
    timeframe_minutes=5,
)

sector_bars = sector_provider.get_bars(sector_request)
sector_raw = candles_to_frame(sector_bars)

sector_context = build_context_returns(
    sector_raw[
        [
            "timestamp",
            "symbol",
            "close",
        ]
    ].rename(
        columns={"symbol": "sector_index_symbol"}
    ),
    key_column="sector_index_symbol",
)

sector_mapping = (
    SectorMapping(
        symbol="RELIANCE",
        sector_index_symbol="NIFTY_OIL_AND_GAS",
        effective_from=date(2026, 9, 9),
    ),
)

print("    Sector:", sector_request.symbol)
print("    Provider symbol:",
      sector_provider.provenance(sector_request)["provider_symbol"])
print("    Context rows:", len(sector_context))
print("    First:", sector_context["timestamp"].min())
print("    Last:", sector_context["timestamp"].max())


# ---------------------------------------------------------------------
# 4. BUILD PHASE 9 DATASET
# ---------------------------------------------------------------------

print("\n[4] Building Phase 9 dataset...")

result = build_phase9_dataset(
    historical_dataset,
    market_context=market_context,
    sector_context=sector_context,
    sector_mappings=sector_mapping,
)

print("\n" + "=" * 72)
print("PHASE 9 — REAL DATA RESULT")
print("=" * 72)

print("Feature observations:", result.feature_rows)
print("Eligible observations:", result.eligible_rows)
print("Excluded observations:", result.excluded_rows)



print("\nExclusion reasons:")
for reason, count in result.exclusion_reasons:
    print(f"  {reason:<32} {count:>5}")

assert sum(
    count for _, count in result.exclusion_reasons
) == result.excluded_rows
print("Training rows:        ", len(result.training_dataset.data))
print("Feature count:        ", len(result.training_dataset.feature_columns))

print("\nLabel distribution:")

distribution = result.label_distribution

for label, count in distribution.items():
    percentage = (
        100.0 * count / len(result.training_dataset.data)
        if len(result.training_dataset.data)
        else 0.0
    )
    print(f"  {label:<20} {count:>5} ({percentage:6.2f}%)")


print("\nFinal dataset columns:")
print(list(result.training_dataset.data.columns))


print("\nFeature NaN counts:")

nan_counts = (
    result.training_dataset.data[
        list(result.training_dataset.feature_columns)
    ]
    .isna()
    .sum()
)

nan_counts = nan_counts[nan_counts > 0].sort_values(ascending=False)

if nan_counts.empty:
    print("  None")
else:
    print(nan_counts)


# ---------------------------------------------------------------------
# 5. SECTOR-CONTEXT QUALITY CHECK
# ---------------------------------------------------------------------

print("\n" + "=" * 72)
print("SECTOR CONTEXT QUALITY CHECK")
print("=" * 72)

sector_columns = [
    "sector_return_1",
    "sector_return_3",
    "sector_return_12",
    "sector_volatility_20",
    "stock_vs_sector_return_1",
]

training_data = result.training_dataset.data

sector_nan = training_data[sector_columns].isna().sum()

print("\nSector feature NaN counts:")
print(sector_nan)

print("\nSector feature non-NaN counts:")
print(training_data[sector_columns].notna().sum())

if sector_nan.eq(len(training_data)).any():
    raise AssertionError(
        "At least one sector feature is still 100% NaN"
    )

print("\nPASS: sector context is populated.")


# ---------------------------------------------------------------------
# 6. BASIC DATASET ACCOUNTING
# ---------------------------------------------------------------------

assert (
    result.feature_rows
    == result.eligible_rows + result.excluded_rows
)

assert len(result.training_dataset.data) == result.eligible_rows

print("\nPASS: dataset accounting is consistent.")

print("\n" + "=" * 72)
print("SMOKE TEST COMPLETE")
print("=" * 72)