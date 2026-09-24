from __future__ import annotations

from datetime import date

import pandas as pd

from market.data.historical.models import HistoricalDataRequest
import scripts.phase9_sector_context as sector_script


def test_phase9_sector_context_uses_upstox_and_timezone_aware_window(monkeypatch):
    class FakeMembership:
        def __init__(self, _mappings):
            pass

        def resolve_many(self, *, symbols, as_of, require_complete):
            assert symbols == ["RELIANCE"]
            assert as_of == date(2026, 7, 15)
            assert require_complete is False
            return [type("Resolution", (), {"sector_index_symbol": "NIFTY_IT"})()]

    captured = {}

    def fake_build(provider, *, symbols, timeframe_minutes, start, end):
        captured.update(
            provider=provider,
            symbols=symbols,
            timeframe_minutes=timeframe_minutes,
            start=start,
            end=end,
        )
        return pd.DataFrame({"timestamp": []})

    monkeypatch.setattr(sector_script, "PointInTimeSectorMembershipProvider", FakeMembership)
    monkeypatch.setattr(sector_script, "load_sector_mappings_csv", lambda _path: [])
    monkeypatch.setattr(sector_script, "build_sector_context", fake_build)

    result = sector_script.build_phase9_sector_context_for_date(
        symbols=["RELIANCE"],
        as_of=date(2026, 7, 15),
        access_token="test-token",
    )

    assert result.empty
    assert captured["symbols"] == ["NIFTY_IT"]
    assert captured["timeframe_minutes"] == 5

    request = HistoricalDataRequest(
        symbol="NIFTY_IT",
        exchange="NSE",
        timeframe_minutes=5,
        start=captured["start"],
        end=captured["end"],
    )
    assert captured["provider"].provenance(request)["instrument_key"] == (
        "NSE_INDEX|Nifty IT"
    )
    assert captured["start"].tzinfo is not None
    assert captured["end"].tzinfo is not None
    assert str(captured["start"].tzinfo) == "Asia/Kolkata"
    assert str(captured["end"].tzinfo) == "Asia/Kolkata"


def test_phase9_sector_context_requires_access_token(monkeypatch):
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)

    class FakeMembership:
        def __init__(self, _mappings):
            pass

        def resolve_many(self, *, symbols, as_of, require_complete):
            return [type("Resolution", (), {"sector_index_symbol": "NIFTY_IT"})()]

    monkeypatch.setattr(sector_script, "PointInTimeSectorMembershipProvider", FakeMembership)
    monkeypatch.setattr(sector_script, "load_sector_mappings_csv", lambda _path: [])

    try:
        sector_script.build_phase9_sector_context_for_date(
            symbols=["RELIANCE"],
            as_of=date(2026, 7, 15),
        )
    except ValueError as exc:
        assert "access_token" in str(exc)
    else:
        raise AssertionError("missing Upstox access token was accepted")
