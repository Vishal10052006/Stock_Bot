"""Tests for the provider-neutral normalized fundamental CSV adapter."""
from __future__ import annotations

import pandas as pd

from intelligence.analysis.fundamentals.csv_provider import CsvFundamentalProvider


def test_csv_provider_loads_and_normalizes_symbol(tmp_path) -> None:
    path = tmp_path / "fundamentals.csv"
    pd.DataFrame(
        [
            {
                "symbol": "reliance",
                "period_start": "2026-04-01T00:00:00+05:30",
                "period_end": "2026-06-30T00:00:00+05:30",
                "published_at": "2026-07-20T18:00:00+05:30",
                "available_at": "2026-07-20T18:01:00+05:30",
                "revenue": 1000,
                "net_income": 120,
                "source": "test",
                "source_version": "v1",
            }
        ]
    ).to_csv(path, index=False)

    snapshots = CsvFundamentalProvider(path).snapshots("RELIANCE")
    assert len(snapshots) == 1
    assert snapshots[0].symbol == "RELIANCE"
    assert snapshots[0].metrics["revenue"] == 1000.0
