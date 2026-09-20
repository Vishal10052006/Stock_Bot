"""Build the real Phase 9 supervised training dataset from live market data.

This is the multi-symbol, multi-date driver that was missing from the repo.
It composes existing, tested Phase 0-9 components — it does not introduce
any new business logic:

    build_point_in_time_universe()   -> PIT symbol universe per as_of date
    UpstoxHistoricalMarketDataProvider -> real 5-minute NSE candles
    build_context_returns()          -> NIFTY 50 market context
    build_phase9_dataset()           -> per-symbol causal features + labels

Run this LOCALLY, where you have:
    - UPSTOX_ACCESS_TOKEN set in the environment
    - the Upstox NSE instrument master at data/reference/upstox/NSE.json.gz
      (see market/data/historical/point_in_time_universe.py for the
      expected format/path; override with --upstox-master if yours lives
      elsewhere)
    - network access to Upstox, NSE bhavcopy, and the NSE security master

This environment (the sandbox this was written in) has none of the above,
so this script has NOT been executed end-to-end here. It has been checked
for import correctness and argument wiring against the actual APIs in this
repo, but you are the first one to actually run it.

Usage:
    PYTHONPATH="$PWD" python3 scripts/build_phase9_real_dataset.py

Output:
    - Prints the same audit table shape as the frozen research report
      (feature_rows / eligible_rows / excluded_rows / label distribution /
      accounting check).
    - Writes the concatenated TrainingDataset to
      data/research/phase9_dataset_<run_id>.parquet (git-ignored — do not
      commit real market data).
    - Writes a JSON audit sidecar next to it with the exact numbers, so the
      research-audit standard (Section 27) has something real to cite.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from market.data.context import (  # noqa: E402
    build_context_returns,
    load_sector_mappings_csv,
)
from scripts.phase9_sector_context import build_phase9_sector_context_for_date  # noqa: E402
from market.data.historical.adapters.upstox import (  # noqa: E402
    UpstoxHistoricalMarketDataProvider,
)
from market.data.historical.liquidity import LiquidityPolicy  # noqa: E402
from market.data.historical.models import HistoricalDataRequest  # noqa: E402
from market.data.historical.pipeline import (  # noqa: E402
    HistoricalMarketDataPipeline,
)
from market.data.historical.point_in_time_universe import (  # noqa: E402
    build_point_in_time_universe,
)
from market.data.historical.universe import UniversePolicy  # noqa: E402
from market.data.ingestion.providers.upstox.instrument_mapper import (  # noqa: E402
    UpstoxInstrumentMapper,
)
from ml.datasets.pipeline import build_phase9_dataset  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")

# ---------------------------------------------------------------------
# Research-run configuration.
#
# These are the same 5 historical dates cited in the prior (unverified)
# summary. They are arbitrary sampling points, not a frozen spec value —
# change them freely. Keep them spread across regimes/weeks per Section 15
# (no tuning on a single narrow window).
# ---------------------------------------------------------------------
DEFAULT_HISTORICAL_DATES: tuple[date, ...] = (
    date(2026, 6, 29),
    date(2026, 7, 15),
    date(2026, 8, 5),
    date(2026, 8, 26),
    date(2026, 9, 11),
)

SYMBOLS_PER_DATE = 25
RANDOM_SEED = 42

# Liquidity/universe policy — adjust to taste, but keep versioned and do
# not silently retune after seeing results (Section 15).
#
# The ADV floor here is INR 500 crore, not INR 50 lakh. INR 50 lakh average
# daily traded value barely filters anything on NSE and would let thin,
# hard-to-fill microcaps into a universe meant to back a strategy with
# INR 75,000 max gross notional and realistic-fill assumptions (frozen
# spec, Section 1). INR 500 crore matches the only precedent that already
# exists in this repo for a real "audit" run
# (tests/test_historical_universe.py: LiquidityPolicy(
#     version="liquidity-audit-2026-09-05", ..., minimum_average_traded_value=5_000_000_000.0)),
# and produces a universe size in the large/mid-cap range consistent with
# the ~106-symbol figure the (unverified) prior Phase-9 summary cited.
# This is still a research assumption, not frozen policy -- see Section 13
# (Execution Capacity Research) before treating it as final.
LIQUIDITY_POLICY = LiquidityPolicy(
    version="liquidity_v1.1",
    lookback_sessions=20,
    minimum_completed_sessions=15,
    minimum_average_traded_value=5_000_000_000.0,  # INR 500 crore ADV floor
)
UNIVERSE_POLICY = UniversePolicy(
    version="universe_v1.0",
    name="nse_eq_liquid_v1",
)

NIFTY_50_INSTRUMENT_KEY = "NSE_INDEX|Nifty 50"

SECTOR_MAPPING_PATH = (
    REPO_ROOT
    / "data/reference/nse/sector_membership/sector_membership.csv"
)


# Calendar days of history fetched BEFORE as_of, purely so indicators with
# real lookback requirements (EMA-50, ATR-14, 20-bar structural swing
# high/low) have enough real prior bars to warm up before the as-of
# session starts. Decision rows are still pinned to the as_of date only
# -- see _session_window() and the post-build filter in main() below.
# Without this padding, build_phase9_dataset legitimately excludes most
# of the first ~4 hours of every session (EMA-50 alone needs 50 completed
# 5-minute bars = ~4h10m) because there is nothing wrong with the data,
# there just isn't enough of it yet on that calendar day alone.
LOOKBACK_DAYS = 15


def _session_window(as_of: date) -> tuple[datetime, datetime]:
    """Return the 09:15-15:30 IST session window for as_of, as UTC-aware datetimes."""
    start = datetime.combine(as_of, time(9, 15), tzinfo=IST)
    end = datetime.combine(as_of, time(15, 30), tzinfo=IST)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _fetch_window(as_of: date) -> tuple[datetime, datetime]:
    """Return the padded fetch window: LOOKBACK_DAYS before as_of through
    the end of the as_of session.

    This is only for candle retrieval (indicator warm-up). Which decision
    rows actually count for as_of happens afterward, in main(), by
    filtering the built dataset down to rows whose own timestamp falls on
    as_of. Candles from the lookback days are never treated as decision
    rows themselves.
    """
    _, session_end = _session_window(as_of)
    lookback_start = datetime.combine(
        as_of - timedelta(days=LOOKBACK_DAYS), time.min, tzinfo=IST
    ).astimezone(timezone.utc)
    return lookback_start, session_end


def _sample_symbols(universe_symbols: tuple[str, ...], as_of: date, n: int) -> list[str]:
    """Deterministically sample up to n symbols, seeded per-date for reproducibility."""
    rng = random.Random(f"{RANDOM_SEED}-{as_of.isoformat()}")
    pool = list(universe_symbols)
    rng.shuffle(pool)
    return sorted(pool[:n])


def _fetch_index_candles(
    access_token: str,
    as_of: date,
) -> pd.DataFrame:
    """Fetch NIFTY 50 5-minute candles for as_of and return an OHLCV frame.

    The Upstox historical adapter hard-validates exchange == "NSE" and only
    uses the request.symbol to look up an instrument_key via its mapper —
    it does not use the exchange field for routing. So the index is fetched
    with its own single-entry instrument mapper (symbol "NIFTY50" ->
    "NSE_INDEX|Nifty 50") and exchange="NSE" to satisfy that validation,
    not because the index is actually an NSE equity.
    """
    index_mapper = UpstoxInstrumentMapper({"NIFTY50": NIFTY_50_INSTRUMENT_KEY})
    index_provider = UpstoxHistoricalMarketDataProvider(
        access_token=access_token,
        instrument_mapper=index_mapper,
    )

    start, end = _fetch_window(as_of)

    request = HistoricalDataRequest(
        symbol="NIFTY50",
        exchange="NSE",
        timeframe_minutes=5,
        start=start,
        end=end,
    )
    bars = index_provider.get_bars(request)

    return pd.DataFrame(
        [
            {
                "timestamp": bar.timestamp,
                "close": bar.close,
            }
            for bar in bars
        ]
    )


def _fetch_symbol_dataset(
    pipeline: HistoricalMarketDataPipeline,
    symbol: str,
    as_of: date,
):
    start, end = _fetch_window(as_of)
    request = HistoricalDataRequest(
        symbol=symbol,
        exchange="NSE",
        timeframe_minutes=5,
        start=start,
        end=end,
    )
    result = pipeline.ingest(request)
    return result.dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upstox-master",
        default="data/reference/upstox/NSE.json.gz",
        help="Path to the Upstox NSE instrument master (gzip JSON).",
    )
    parser.add_argument(
        "--out-dir",
        default="data/research",
        help="Directory to write the output dataset + audit JSON into.",
    )
    parser.add_argument(
        "--symbols-per-date",
        type=int,
        default=SYMBOLS_PER_DATE,
    )
    args = parser.parse_args()

    access_token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise SystemExit(
            "UPSTOX_ACCESS_TOKEN must be set in the environment. "
            "Do not hardcode it into this script or paste it into chat."
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    print("=" * 72)
    print("PHASE 9 — REAL MULTI-SYMBOL DATASET BUILD")
    print("=" * 72)
    print(f"Dates: {[d.isoformat() for d in DEFAULT_HISTORICAL_DATES]}")
    print(f"Symbols/date: {args.symbols_per_date}")
    print(f"Run id: {run_id}")

    all_feature_frames: list[pd.DataFrame] = []
    sector_mappings = load_sector_mappings_csv(SECTOR_MAPPING_PATH)

    total_feature_rows = 0
    total_eligible_rows = 0
    total_excluded_rows = 0
    total_session_filtered_out = 0
    exclusion_totals: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    symbols_used: set[str] = set()
    per_date_audit: list[dict] = []

    for as_of in DEFAULT_HISTORICAL_DATES:
        print(f"\n--- {as_of.isoformat()} ---")

        universe = build_point_in_time_universe(
            as_of=as_of,
            liquidity_policy=LIQUIDITY_POLICY,
            universe_policy=UNIVERSE_POLICY,
            upstox_master_path=args.upstox_master,
        )

        if not universe.identities:
            print(f"  No eligible/mapped symbols for {as_of}; skipping.")
            per_date_audit.append(
                {"as_of": as_of.isoformat(), "symbols_sampled": 0, "reason": "empty_universe"}
            )
            continue

        instrument_mapping = {
            identity.symbol: identity.upstox_instrument_key
            for identity in universe.identities
            if identity.upstox_instrument_key is not None
        }
        instrument_mapper = UpstoxInstrumentMapper(instrument_mapping)

        provider = UpstoxHistoricalMarketDataProvider(
            access_token=access_token,
            instrument_mapper=instrument_mapper,
        )
        pipeline = HistoricalMarketDataPipeline(
            provider,
            require_complete_sessions=False,
        )

        sampled_symbols = _sample_symbols(
            tuple(instrument_mapping.keys()),
            as_of,
            args.symbols_per_date,
        )
        print(f"  Universe size: {len(instrument_mapping)}; sampled: {len(sampled_symbols)}")
        print(f"  Sampled symbols: {sampled_symbols}")

        # Market context: NIFTY 50 for this session.
        try:
            index_frame = _fetch_index_candles(access_token, as_of)
            if index_frame.empty:
                print("  WARNING: empty NIFTY 50 candle set; skipping this date.")
                continue
            market_context = build_context_returns(index_frame, price_column="close")
        except Exception as exc:  # noqa: BLE001 - surface and skip this date
            print(f"  WARNING: failed to build market context for {as_of}: {exc}")
            continue

        date_eligible = 0
        date_excluded = 0
        date_rows_kept = 0

        for symbol in sampled_symbols:
            try:
                historical_dataset = _fetch_symbol_dataset(pipeline, symbol, as_of)
            except Exception as exc:  # noqa: BLE001 - one bad symbol shouldn't kill the run
                print(f"    {symbol}: SKIPPED (fetch/validation failed: {exc})")
                continue

            try:
                sector_context = build_phase9_sector_context_for_date(
                    provider=provider,
                    symbols=[symbol],
                    as_of=as_of,
                    lookback_days=LOOKBACK_DAYS,
                )

                if sector_context.empty:
                    sector_context = None

                result = build_phase9_dataset(
                    historical_dataset,
                    market_context=market_context,
                    sector_context=sector_context,
                    sector_mappings=sector_mappings,
                )
            except ValueError as exc:
                # e.g. "no eligible decision rows" for a quiet/short session
                print(f"    {symbol}: SKIPPED (no eligible rows: {exc})")
                continue

            symbols_used.add(symbol)
            total_feature_rows += result.feature_rows
            total_eligible_rows += result.eligible_rows
            total_excluded_rows += result.excluded_rows
            date_eligible += result.eligible_rows
            date_excluded += result.excluded_rows

            for reason, count in result.exclusion_reasons:
                exclusion_totals[reason] = exclusion_totals.get(reason, 0) + count

            # result.eligible_rows/exclusion_reasons cover the WHOLE padded
            # fetch window (lookback days included, for indicator warm-up).
            # Only rows whose own timestamp is actually on as_of are kept
            # as decision rows for this as-of date -- the lookback days'
            # rows exist purely so those as_of rows have real history
            # behind them, they are never themselves counted as decisions.
            frame = result.training_dataset.data.copy()
            frame = frame.loc[frame["timestamp"].dt.date == as_of].copy()

            dropped_outside_session = result.eligible_rows - len(frame)
            total_session_filtered_out += dropped_outside_session

            if frame.empty:
                print(
                    f"    {symbol}: 0 rows fall on {as_of.isoformat()} itself "
                    f"(pipeline eligible={result.eligible_rows}, all from "
                    "lookback padding) -- skipped"
                )
                continue

            frame["as_of_date"] = as_of.isoformat()
            all_feature_frames.append(frame)

            for label, count in frame["label"].value_counts().items():
                label_counts[str(label)] = label_counts.get(str(label), 0) + int(count)

            date_rows_kept += len(frame)

            print(
                f"    {symbol}: pipeline feature_rows={result.feature_rows} "
                f"eligible={result.eligible_rows} excluded={result.excluded_rows} "
                f"| rows on {as_of.isoformat()}: {len(frame)}"
            )

        per_date_audit.append(
            {
                "as_of": as_of.isoformat(),
                "symbols_sampled": len(sampled_symbols),
                "pipeline_eligible_rows": date_eligible,
                "pipeline_excluded_rows": date_excluded,
                "decision_rows_kept_on_as_of_date": date_rows_kept,
            }
        )

    if not all_feature_frames:
        raise SystemExit(
            "No data was successfully built for any date/symbol. "
            "Check UPSTOX_ACCESS_TOKEN, the instrument master path, and network access."
        )

    combined = pd.concat(all_feature_frames, ignore_index=True)

    accounting_ok = (total_eligible_rows + total_excluded_rows) == total_feature_rows

    print("\n" + "=" * 72)
    print("AUDIT SUMMARY")
    print("=" * 72)
    print(f"Pipeline feature rows (incl. {LOOKBACK_DAYS}d lookback padding): "
          f"{total_feature_rows}")
    print(f"Pipeline eligible rows (incl. lookback padding): {total_eligible_rows}")
    print(f"Pipeline excluded rows (incl. lookback padding): {total_excluded_rows}")
    print(f"Pipeline accounting check: "
          f"{total_eligible_rows} + {total_excluded_rows} = {total_eligible_rows + total_excluded_rows} "
          f"vs feature_rows={total_feature_rows} -> {'PASS' if accounting_ok else 'FAIL'}")
    print(f"Eligible rows dropped for being outside the as-of date itself "
          f"(lookback-padding rows, not decisions): {total_session_filtered_out}")
    print(f"FINAL decision rows kept (on their as-of date, this is the "
          f"actual dataset size): {len(combined)}")
    print(f"Unique symbols used:     {len(symbols_used)}")
    print(f"Historical dates:        {len(DEFAULT_HISTORICAL_DATES)}")
    print(f"Exclusion reasons (pipeline-level, incl. lookback padding): {exclusion_totals}")
    print(f"Label distribution (FINAL dataset only):      {label_counts}")

    dataset_path = out_dir / f"phase9_dataset_{run_id}.parquet"
    combined.to_parquet(dataset_path, index=False)

    audit = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dates": [d.isoformat() for d in DEFAULT_HISTORICAL_DATES],
        "symbols_per_date_requested": args.symbols_per_date,
        "unique_symbols_used": sorted(symbols_used),
        "lookback_days": LOOKBACK_DAYS,
        "pipeline_feature_rows_incl_lookback": total_feature_rows,
        "pipeline_eligible_rows_incl_lookback": total_eligible_rows,
        "pipeline_excluded_rows_incl_lookback": total_excluded_rows,
        "pipeline_accounting_check_passed": accounting_ok,
        "rows_dropped_outside_as_of_date": total_session_filtered_out,
        "final_decision_rows": len(combined),
        "exclusion_reasons_incl_lookback": exclusion_totals,
        "label_distribution_final_dataset": label_counts,
        "per_date_audit": per_date_audit,
        "liquidity_policy": asdict(LIQUIDITY_POLICY),
        "universe_policy": asdict(UNIVERSE_POLICY),
        "dataset_file": dataset_path.name,
    }
    audit_path = out_dir / f"phase9_dataset_{run_id}.audit.json"
    audit_path.write_text(json.dumps(audit, indent=2))

    print(f"\nDataset written to: {dataset_path}")
    print(f"Audit written to:   {audit_path}")
    print("\nSend both files back for the Logistic Regression baseline step.")


if __name__ == "__main__":
    main()