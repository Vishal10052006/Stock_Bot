from pathlib import Path

import pandas as pd
import pytest

from scripts.trading.run_empirical_paper import _load_rows, _load_sidecar


def _row(timestamp: str) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "symbol": "RELIANCE",
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


def test_empirical_loader_requires_preordered_rows(tmp_path: Path) -> None:
    path = tmp_path / "rows.parquet"
    pd.DataFrame(
        [_row("2026-09-21T10:05:00Z"), _row("2026-09-21T10:00:00Z")]
    ).to_parquet(path)
    with pytest.raises(ValueError, match="chronological order"):
        _load_rows(path)


def test_empirical_loader_rejects_duplicate_symbol_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "rows.parquet"
    pd.DataFrame(
        [_row("2026-09-21T10:00:00Z"), _row("2026-09-21T10:00:00Z")]
    ).to_parquet(path)
    with pytest.raises(ValueError, match="duplicate"):
        _load_rows(path)


def test_empirical_loader_normalizes_symbol_and_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "rows.parquet"
    row = _row("2026-09-21T10:00:00+05:30")
    row["symbol"] = " reliance "
    pd.DataFrame([row]).to_parquet(path)
    frame = _load_rows(path)
    assert frame.loc[0, "symbol"] == "RELIANCE"
    assert str(frame.loc[0, "timestamp"].tz) == "UTC"


def test_sidecar_must_be_object(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        _load_sidecar(path)
