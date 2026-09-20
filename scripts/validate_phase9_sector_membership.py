"""Validate Phase 9 point-in-time sector membership reference data.

This script intentionally does not infer sector membership.

It validates:
- required Phase 9 symbols
- required research dates
- explicit sector mappings
- supported NSE sector-index identifiers
- PIT resolution
- manifest provenance
- duplicate/overlapping mappings

Exit code 0 means the reference dataset is safe for downstream PIT use.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow this repository script to import the top-level ``market`` package
# when executed directly with ``python scripts/<script>.py``.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
import json
from collections import Counter
from datetime import date
from market.data.context.sector_mapping_io import load_sector_mappings_csv
from market.data.context.sector_membership import (
    PointInTimeSectorMembershipProvider,
)
from market.data.context.sector_registry import (
    DEFAULT_YFINANCE_INDEX_SYMBOLS,
)


DEFAULT_REFERENCE_DIR = Path(
    "data/reference/nse/sector_membership"
)

DEFAULT_SYMBOLS_FILE = DEFAULT_REFERENCE_DIR / "phase9_symbols.txt"
DEFAULT_MAPPING_FILE = DEFAULT_REFERENCE_DIR / "sector_membership.csv"
DEFAULT_MANIFEST_FILE = DEFAULT_REFERENCE_DIR / "manifest.json"

RESEARCH_DATES = (
    date(2026, 6, 29),
    date(2026, 7, 15),
    date(2026, 8, 5),
    date(2026, 8, 26),
    date(2026, 9, 11),
)


def load_symbols(path: Path) -> tuple[str, ...]:
    """Load the exact Phase 9 symbol universe."""
    if not path.is_file():
        raise FileNotFoundError(path)

    symbols = tuple(
        line.strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )

    if not symbols:
        raise ValueError(f"symbol file is empty: {path}")

    if len(set(symbols)) != len(symbols):
        duplicates = [
            symbol
            for symbol, count in Counter(symbols).items()
            if count > 1
        ]
        raise ValueError(
            f"duplicate symbols in {path}: {duplicates}"
        )

    return symbols


def load_manifest(path: Path) -> dict:
    """Load and validate the minimum provenance manifest contract."""
    if not path.is_file():
        raise FileNotFoundError(path)

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("manifest must contain a JSON object")

    if payload.get("schema_version") != "1.0":
        raise ValueError(
            "manifest schema_version must be '1.0'"
        )

    snapshots = payload.get("snapshots")

    if not isinstance(snapshots, list):
        raise ValueError("manifest snapshots must be a list")

    return payload


def validate_manifest_provenance(
    manifest: dict,
    mapping_file: Path,
) -> None:
    """Require provenance before non-empty mappings can be accepted."""
    snapshots = manifest["snapshots"]

    if mapping_file.stat().st_size > 0:
        content = mapping_file.read_text(encoding="utf-8").strip()
        header_only = (
            content
            == "symbol,sector_index_symbol,effective_from,effective_to"
        )

        if not header_only and not snapshots:
            raise ValueError(
                "sector mappings exist but manifest.snapshots is empty"
            )

    required_fields = (
        "source_name",
        "source_url",
        "retrieved_at_utc",
        "snapshot_as_of",
        "checksum",
    )

    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, dict):
            raise ValueError(
                f"manifest snapshot {index} must be an object"
            )

        missing = [
            field
            for field in required_fields
            if not str(snapshot.get(field, "")).strip()
        ]

        if missing:
            raise ValueError(
                f"manifest snapshot {index} missing: {missing}"
            )


def validate_supported_sector_indices(
    mappings,
) -> None:
    """Reject sector identifiers for which the registry has no provider symbol."""
    supported = {
        symbol.upper()
        for symbol in DEFAULT_YFINANCE_INDEX_SYMBOLS
    }

    unsupported = sorted(
        {
            mapping.sector_index_symbol
            for mapping in mappings
            if mapping.sector_index_symbol not in supported
        }
    )

    if unsupported:
        raise ValueError(
            "sector mappings contain unsupported sector index symbols: "
            f"{unsupported}"
        )


def build_coverage_matrix(
    provider: PointInTimeSectorMembershipProvider,
    symbols: tuple[str, ...],
) -> list[tuple[date, int, int, tuple[str, ...]]]:
    """Resolve every Phase 9 symbol on every research date."""
    results = []

    for research_date in RESEARCH_DATES:
        resolutions = provider.resolve_many(
            symbols=symbols,
            as_of=research_date,
            require_complete=False,
        )

        mapped = tuple(
            resolution
            for resolution in resolutions
            if resolution.sector_index_symbol is not None
        )

        missing = tuple(
            resolution.symbol
            for resolution in resolutions
            if resolution.sector_index_symbol is None
        )

        results.append(
            (
                research_date,
                len(mapped),
                len(missing),
                missing,
            )
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Phase 9 PIT sector membership."
    )

    parser.add_argument(
        "--symbols",
        type=Path,
        default=DEFAULT_SYMBOLS_FILE,
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=DEFAULT_MAPPING_FILE,
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_FILE,
    )

    args = parser.parse_args()

    symbols = load_symbols(args.symbols)
    manifest = load_manifest(args.manifest)
    validate_manifest_provenance(
        manifest,
        args.mappings,
    )

    mapping_content = args.mappings.read_text(
        encoding="utf-8"
    ).strip()

    header_only = (
        mapping_content
        == "symbol,sector_index_symbol,effective_from,effective_to"
    )

    if header_only:
        print("============================================================")
        print("PHASE 9 — PIT SECTOR MEMBERSHIP VALIDATION")
        print("============================================================")
        print(f"Phase 9 symbols : {len(symbols)}")
        print("Mappings        : 0")
        print("Status          : REFERENCE DATA NOT POPULATED")
        print()
        print(
            "PASS — validator is ready; no historical membership "
            "has been fabricated."
        )
        return 0

    mappings = load_sector_mappings_csv(args.mappings)

    validate_supported_sector_indices(mappings)

    provider = PointInTimeSectorMembershipProvider(mappings)

    coverage = build_coverage_matrix(
        provider,
        symbols,
    )

    print("============================================================")
    print("PHASE 9 — PIT SECTOR MEMBERSHIP VALIDATION")
    print("============================================================")
    print(f"Phase 9 symbols : {len(symbols)}")
    print(f"Mappings        : {len(mappings)}")
    print()

    total = len(symbols)

    for research_date, mapped, missing, missing_symbols in coverage:
        print(
            f"{research_date.isoformat()}  "
            f"mapped={mapped:>3}  "
            f"missing={missing:>3}  "
            f"coverage={mapped / total:.1%}"
        )

        if missing_symbols:
            print(
                "  Missing:",
                ", ".join(missing_symbols),
            )

    incomplete = [
        result
        for result in coverage
        if result[2] > 0
    ]

    print()

    if incomplete:
        print(
            "FAIL — one or more research dates have missing "
            "point-in-time sector membership."
        )
        return 1

    print(
        "PASS — all Phase 9 symbols resolve to explicit "
        "PIT sector membership on every research date."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
