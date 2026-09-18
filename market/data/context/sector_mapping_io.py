"""Strict CSV I/O for point-in-time sector mappings."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from market.data.context.models import SectorMapping, validate_sector_mappings


REQUIRED_COLUMNS = (
    "symbol",
    "sector_index_symbol",
    "effective_from",
    "effective_to",
)


def load_sector_mappings_csv(path: str | Path) -> tuple[SectorMapping, ...]:
    """Load and validate explicit point-in-time sector mappings.

    Empty effective_to values represent open-ended mappings. The loader does
    not infer missing memberships and does not apply current classifications
    backward in time.
    """
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)

    frame = pd.read_csv(csv_path, dtype=str)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            "sector mapping CSV missing required columns: "
            f"{missing}"
        )

    mappings: list[SectorMapping] = []
    for row_number, row in frame.iterrows():
        symbol = str(row["symbol"]).strip()
        sector_index_symbol = str(row["sector_index_symbol"]).strip()
        effective_from_raw = str(row["effective_from"]).strip()
        effective_to_raw = str(row["effective_to"]).strip()

        if not symbol or symbol.lower() == "nan":
            raise ValueError(f"row {row_number + 2}: symbol is required")
        if (
            not sector_index_symbol
            or sector_index_symbol.lower() == "nan"
        ):
            raise ValueError(
                f"row {row_number + 2}: sector_index_symbol is required"
            )
        if not effective_from_raw or effective_from_raw.lower() == "nan":
            raise ValueError(
                f"row {row_number + 2}: effective_from is required"
            )

        try:
            effective_from = date.fromisoformat(effective_from_raw)
        except ValueError as exc:
            raise ValueError(
                f"row {row_number + 2}: invalid effective_from "
                f"{effective_from_raw!r}"
            ) from exc

        effective_to = None
        if effective_to_raw and effective_to_raw.lower() != "nan":
            try:
                effective_to = date.fromisoformat(effective_to_raw)
            except ValueError as exc:
                raise ValueError(
                    f"row {row_number + 2}: invalid effective_to "
                    f"{effective_to_raw!r}"
                ) from exc

        mappings.append(
            SectorMapping(
                symbol=symbol,
                sector_index_symbol=sector_index_symbol,
                effective_from=effective_from,
                effective_to=effective_to,
            )
        )

    result = tuple(mappings)
    validate_sector_mappings(result)
    return result
