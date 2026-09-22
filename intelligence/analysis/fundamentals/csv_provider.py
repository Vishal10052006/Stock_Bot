"""CSV adapter for normalized point-in-time fundamental snapshots.

The CSV is deliberately provider-neutral. External acquisition is kept outside
the Analysis Bot so credentials, rate limits and vendor-specific parsing cannot
leak into the analytical layer.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from intelligence.analysis.fundamentals.contracts import FundamentalSnapshot
from intelligence.analysis.fundamentals.provider import FundamentalProvider


class CsvFundamentalProvider:
    """Load normalized fundamental observations from a CSV file."""

    REQUIRED_COLUMNS = frozenset(
        {
            "symbol",
            "period_start",
            "period_end",
            "published_at",
            "available_at",
        }
    )

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def snapshots(self, symbol: str) -> tuple[FundamentalSnapshot, ...]:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        frame = pd.read_csv(self.path)
        missing = self.REQUIRED_COLUMNS.difference(frame.columns)
        if missing:
            raise ValueError(f"fundamental CSV missing columns: {sorted(missing)}")

        normalized = symbol.strip().upper()
        rows = frame.loc[
            frame["symbol"].astype(str).str.strip().str.upper().eq(normalized)
        ]
        snapshots: list[FundamentalSnapshot] = []
        reserved = {
            "symbol",
            "period_start",
            "period_end",
            "published_at",
            "available_at",
            "currency",
            "source",
            "source_version",
            "statement_type",
            "consolidated",
        }
        for row in rows.to_dict(orient="records"):
            metrics = {
                str(key).strip().lower(): value
                for key, value in row.items()
                if key not in reserved and pd.notna(value)
            }
            snapshots.append(
                FundamentalSnapshot(
                    symbol=str(row["symbol"]),
                    period_start=pd.Timestamp(row["period_start"]),
                    period_end=pd.Timestamp(row["period_end"]),
                    published_at=pd.Timestamp(row["published_at"]),
                    available_at=pd.Timestamp(row["available_at"]),
                    metrics=metrics,
                    currency=str(row.get("currency", "INR")),
                    source=str(row.get("source", "csv")),
                    source_version=str(row.get("source_version", "unknown")),
                    statement_type=str(row.get("statement_type", "unknown")),
                    consolidated=(
                        None
                        if pd.isna(row.get("consolidated"))
                        else bool(row.get("consolidated"))
                    ),
                )
            )
        return tuple(
            sorted(
                snapshots,
                key=lambda snapshot: (snapshot.available_at, snapshot.period_end),
            )
        )
