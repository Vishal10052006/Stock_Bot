"""Build causal fixed-horizon return targets aligned to a frozen Phase 9 dataset.

The canonical Phase 9 parquet intentionally contains only decision-time
features plus the existing classification label. This script keeps that
dataset unchanged and creates a separate research target artifact by
re-fetching the real OHLCV candles needed to determine a future close.

Usage:
    PYTHONPATH="$PWD" python scripts/build_phase9_return_target_dataset.py \
      --dataset data/research/phase9_dataset_<run_id>.parquet \
      --horizon-bars 12

Requires UPSTOX_ACCESS_TOKEN and the Upstox NSE instrument master.
Do not commit the resulting real-market parquet.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from market.data.historical.adapters.upstox import (  # noqa: E402
    UpstoxHistoricalMarketDataProvider,
)
from market.data.historical.models import HistoricalDataRequest  # noqa: E402
from market.data.historical.pipeline import (  # noqa: E402
    HistoricalMarketDataPipeline,
)
from market.data.historical.point_in_time_universe import (  # noqa: E402
    build_point_in_time_universe,
)
from market.data.historical.universe import UniversePolicy  # noqa: E402
from market.data.historical.liquidity import LiquidityPolicy  # noqa: E402
from market.data.ingestion.providers.upstox.instrument_mapper import (  # noqa: E402
    UpstoxInstrumentMapper,
)
from ml.datasets.return_targets import (  # noqa: E402
    build_fixed_horizon_return_targets,
)

IST = ZoneInfo("Asia/Kolkata")
LOOKBACK_DAYS = 15
DEFAULT_LIQUIDITY_POLICY = LiquidityPolicy(
    version="liquidity_v1.1",
    lookback_sessions=20,
    minimum_completed_sessions=15,
    minimum_average_traded_value=5_000_000_000.0,
)
DEFAULT_UNIVERSE_POLICY = UniversePolicy(
    version="universe_v1.0",
    name="nse_eq_liquid_v1",
)


def _fetch_window(as_of: date) -> tuple[datetime, datetime]:
    start = datetime.combine(
        as_of - timedelta(days=LOOKBACK_DAYS),
        time.min,
        tzinfo=IST,
    ).astimezone(timezone.utc)
    end = datetime.combine(
        as_of,
        time(15, 30),
        tzinfo=IST,
    ).astimezone(timezone.utc)
    return start, end


def _fetch_symbol_candles(
    *,
    provider: UpstoxHistoricalMarketDataProvider,
    symbol: str,
    as_of: date,
) -> pd.DataFrame:
    start, end = _fetch_window(as_of)
    request = HistoricalDataRequest(
        symbol=symbol,
        exchange="NSE",
        timeframe_minutes=5,
        start=start,
        end=end,
    )
    dataset = HistoricalMarketDataPipeline(
        provider,
        require_complete_sessions=False,
    ).ingest(request).dataset

    return pd.DataFrame(
        [
            {
                "timestamp": bar.timestamp,
                "symbol": bar.symbol,
                "close": bar.close,
            }
            for bar in dataset.bars
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out-dir", default="data/research")
    parser.add_argument("--horizon-bars", type=int, default=12)
    parser.add_argument(
        "--upstox-master",
        default="data/reference/upstox/NSE.json.gz",
    )
    args = parser.parse_args()

    if args.horizon_bars < 1:
        raise SystemExit("--horizon-bars must be >= 1")

    access_token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise SystemExit(
            "UPSTOX_ACCESS_TOKEN must be set in the environment. "
            "Do not hardcode or paste it into chat."
        )

    source_path = Path(args.dataset)
    if not source_path.exists():
        raise SystemExit(f"Dataset not found: {source_path}")

    dataset = pd.read_parquet(source_path)
    required = {"timestamp", "symbol"}
    missing = required.difference(dataset.columns)
    if missing:
        raise SystemExit(
            f"Dataset is missing required columns: {sorted(missing)}"
        )

    dataset["timestamp"] = pd.to_datetime(dataset["timestamp"], errors="raise")
    if not isinstance(dataset["timestamp"].dtype, pd.DatetimeTZDtype):
        raise SystemExit("Dataset timestamps must be timezone-aware.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    all_targets: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []

    date_values = sorted(dataset["timestamp"].dt.date.unique())

    print("=" * 72)
    print("PHASE 9 — CAUSAL RETURN TARGET BUILD")
    print("=" * 72)
    print(f"Source dataset: {source_path}")
    print(f"Horizon bars: {args.horizon_bars}")
    print(f"Dates: {[d.isoformat() for d in date_values]}")

    for as_of in date_values:
        date_rows = dataset.loc[
            dataset["timestamp"].dt.date == as_of,
            ["timestamp", "symbol"],
        ].drop_duplicates(["timestamp", "symbol"])

        universe = build_point_in_time_universe(
            as_of=as_of,
            liquidity_policy=DEFAULT_LIQUIDITY_POLICY,
            universe_policy=DEFAULT_UNIVERSE_POLICY,
            upstox_master_path=args.upstox_master,
        )
        mapping = {
            identity.symbol: identity.upstox_instrument_key
            for identity in universe.identities
            if identity.upstox_instrument_key is not None
        }

        print(f"\n--- {as_of.isoformat()} ({len(date_rows)} decisions) ---")

        for symbol, symbol_rows in date_rows.groupby("symbol", sort=True):
            instrument_key = mapping.get(symbol)
            if instrument_key is None:
                failures.append(
                    {
                        "date": as_of.isoformat(),
                        "symbol": str(symbol),
                        "reason": "NO_PIT_INSTRUMENT_MAPPING",
                    }
                )
                continue

            provider = UpstoxHistoricalMarketDataProvider(
                access_token=access_token,
                instrument_mapper=UpstoxInstrumentMapper(
                    {str(symbol): instrument_key}
                ),
            )

            try:
                candles = _fetch_symbol_candles(
                    provider=provider,
                    symbol=str(symbol),
                    as_of=as_of,
                )

                if candles.empty:
                    raise ValueError("empty candle set")

                decisions = symbol_rows.merge(
                    candles,
                    on=["timestamp", "symbol"],
                    how="left",
                    validate="one_to_one",
                )

                if decisions["close"].isna().any():
                    missing_count = int(decisions["close"].isna().sum())
                    raise ValueError(
                        f"{missing_count} decision timestamps missing in OHLCV"
                    )

                targets = build_fixed_horizon_return_targets(
                    candles,
                    decisions[["timestamp", "symbol", "close"]],
                    horizon_bars=args.horizon_bars,
                )

                if not targets.empty:
                    all_targets.append(targets)

                print(
                    f"  {symbol}: decisions={len(decisions)} "
                    f"targets={len(targets)}"
                )
            except Exception as exc:  # noqa: BLE001 - auditable per-symbol failure
                failures.append(
                    {
                        "date": as_of.isoformat(),
                        "symbol": str(symbol),
                        "reason": str(exc),
                    }
                )
                print(f"  {symbol}: FAILED ({exc})")

    if not all_targets:
        raise SystemExit(
            "No return targets were built. Check Upstox access, "
            "instrument master, and the source dataset."
        )

    result = pd.concat(all_targets, ignore_index=True)
    result = result.sort_values(
        ["timestamp", "symbol"],
        kind="stable",
    ).reset_index(drop=True)

    output_path = out_dir / (
        f"phase9_return_targets_{run_id}_h{args.horizon_bars}.parquet"
    )
    result.to_parquet(output_path, index=False)

    audit = {
        "run_id": run_id,
        "source_dataset": str(source_path),
        "horizon_bars": args.horizon_bars,
        "lookback_days": LOOKBACK_DAYS,
        "source_decision_rows": int(len(dataset)),
        "target_rows": int(len(result)),
        "target_coverage": float(len(result) / len(dataset)),
        "unique_symbols": int(result["symbol"].nunique()),
        "future_timestamp_strictly_after_decision": bool(
            (result["future_timestamp"] > result["timestamp"]).all()
        ),
        "future_return_finite": bool(result["future_return"].map(pd.isna).sum() == 0),
        "failures": failures,
        "output_file": output_path.name,
    }

    audit_path = output_path.with_suffix(".audit.json")
    audit_path.write_text(json.dumps(audit, indent=2))

    print("\n" + "=" * 72)
    print("RETURN TARGET AUDIT")
    print("=" * 72)
    print(f"Source decision rows: {len(dataset)}")
    print(f"Target rows:          {len(result)}")
    print(f"Coverage:             {len(result) / len(dataset):.2%}")
    print(f"Symbols:              {result['symbol'].nunique()}")
    print(f"Failures:             {len(failures)}")
    print(f"Target artifact:      {output_path}")
    print(f"Audit artifact:       {audit_path}")


if __name__ == "__main__":
    main()
