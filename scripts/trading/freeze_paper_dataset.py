"""Freeze and fingerprint a strategy-ready paper dataset.

This command creates metadata only; it never rewrites the source parquet.
The resulting manifest is the identity boundary used by EMP-01.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = (
    "timestamp",
    "symbol",
    "close",
    "regime",
    "regime_probability",
    "vwap_distance_pct",
    "rvol_20",
    "higher_high",
    "higher_low",
    "lower_low",
    "lower_high",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_dataset(path: str | Path) -> dict[str, object]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    frame = pd.read_parquet(source)
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"paper dataset is missing required columns: {missing}")
    if frame.empty:
        raise ValueError("paper dataset is empty")

    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    if timestamps.isna().any():
        raise ValueError("paper dataset contains missing timestamps")
    if not timestamps.is_monotonic_increasing:
        raise ValueError("paper dataset must be chronologically ordered")
    if frame.duplicated(["timestamp", "symbol"]).any():
        raise ValueError("paper dataset contains duplicate timestamp/symbol rows")

    symbols = frame["symbol"].astype(str).str.strip().str.upper()
    if (symbols == "").any():
        raise ValueError("paper dataset contains an empty symbol")
    if (pd.to_numeric(frame["close"], errors="coerce") <= 0).any():
        raise ValueError("paper dataset contains non-positive close prices")

    return {
        "sha256": sha256_file(source),
        "path": str(source),
        "rows": int(len(frame)),
        "symbols": sorted(symbols.unique().tolist()),
        "period_start": timestamps.min().isoformat(),
        "period_end": timestamps.max().isoformat(),
        "columns": list(frame.columns),
        "required_columns": list(REQUIRED_COLUMNS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    metadata = validate_dataset(args.input)
    manifest = {
        "manifest_version": "PAPER-DATASET-MANIFEST-v1",
        "dataset_version": args.dataset_version,
        "artifact": metadata,
    }

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("=" * 72)
    print("STOCK BOT — PAPER DATASET FREEZE")
    print("=" * 72)
    print(f"Dataset version : {args.dataset_version}")
    print(f"Rows            : {metadata['rows']:,}")
    print(f"Symbols         : {len(metadata['symbols']):,}")
    print(f"Period          : {metadata['period_start']} -> {metadata['period_end']}")
    print(f"SHA-256         : {metadata['sha256']}")
    print(f"Manifest        : {target}")
    print("=" * 72)


if __name__ == "__main__":
    main()
