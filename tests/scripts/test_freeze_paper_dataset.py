from pathlib import Path

import pandas as pd
import pytest

from scripts.trading.freeze_paper_dataset import validate_dataset


def _row(timestamp: str, symbol: str = "RELIANCE") -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "close": 100.0,
        "regime": "TREND_UP",
        "regime_probability": 0.9,
        "vwap_distance_pct": 0.5,
        "rvol_20": 1.4,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }


def test_freeze_validation_returns_deterministic_file_identity(tmp_path: Path) -> None:
    path = tmp_path / "paper.parquet"
    pd.DataFrame([_row("2026-09-21T10:00:00Z"), _row("2026-09-21T10:05:00Z")]).to_parquet(path)

    first = validate_dataset(path)
    second = validate_dataset(path)

    assert first["sha256"] == second["sha256"]
    assert first["rows"] == 2
    assert first["symbols"] == ["RELIANCE"]


@pytest.mark.parametrize(
    "rows,error",
    [
        ([_row("2026-09-21T10:05:00Z"), _row("2026-09-21T10:00:00Z")], "chronologically"),
        ([_row("2026-09-21T10:00:00Z"), _row("2026-09-21T10:00:00Z")], "duplicate"),
    ],
)
def test_freeze_validation_rejects_bad_order_or_duplicates(
    tmp_path: Path, rows: list[dict[str, object]], error: str
) -> None:
    path = tmp_path / "paper.parquet"
    pd.DataFrame(rows).to_parquet(path)

    with pytest.raises(ValueError, match=error):
        validate_dataset(path)
