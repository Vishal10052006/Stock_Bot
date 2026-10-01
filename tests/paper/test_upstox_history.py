from __future__ import annotations

import pandas as pd

from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper
from trading.paper.upstox_history import UpstoxHistoryProvider


def _provider() -> UpstoxHistoryProvider:
    """Build a deterministic provider fixture without network access."""
    mapper = UpstoxInstrumentMapper(
        {
            "RELIANCE": "NSE_EQ|INE002A01018",
        }
    )
    return UpstoxHistoryProvider(
        access_token="token",
        instrument_mapper=mapper,
        lookback_days=5,
    )


def _raw_candles():
    """Return rows before, at, and after a causal decision timestamp."""
    return [
        ["2026-09-30T09:10:00+05:30", 100, 101, 99, 100.5, 1000, 0],
        ["2026-09-30T09:15:00+05:30", 100.5, 102, 100, 101, 1100, 0],
        ["2026-09-30T09:20:00+05:30", 101, 103, 100.5, 102, 1200, 0],
        ["2026-09-30T09:25:00+05:30", 102, 104, 101, 103, 1300, 0],
    ]


def test_upstox_history_provider_filters_future_rows(monkeypatch) -> None:
    provider = _provider()

    monkeypatch.setattr(
        provider,
        "_fetch",
        lambda instrument_key, cutoff: _raw_candles(),
    )

    frame = provider.frame(
        "RELIANCE",
        pd.Timestamp("2026-09-30T09:20:00+05:30"),
    )

    assert list(frame["timestamp"]) == [
        pd.Timestamp("2026-09-30T03:40:00+00:00"),
        pd.Timestamp("2026-09-30T03:45:00+00:00"),
    ]
    assert (frame["timestamp"] < pd.Timestamp("2026-09-30T03:50:00+00:00")).all()


def test_upstox_history_provider_includes_decision_timestamp_for_benchmark(
    monkeypatch,
) -> None:
    """Benchmark context may include T, but never any observation after T."""
    provider = _provider()

    monkeypatch.setattr(
        provider,
        "_fetch",
        lambda instrument_key, cutoff: _raw_candles(),
    )

    cutoff = pd.Timestamp("2026-09-30T09:20:00+05:30")
    frame = provider.frame_through("RELIANCE", cutoff)

    assert list(frame["timestamp"]) == [
        pd.Timestamp("2026-09-30T03:40:00+00:00"),
        pd.Timestamp("2026-09-30T03:45:00+00:00"),
        pd.Timestamp("2026-09-30T03:50:00+00:00"),
    ]
    assert frame["timestamp"].max() == pd.Timestamp("2026-09-30T03:50:00+00:00")
    assert (frame["timestamp"] <= pd.Timestamp("2026-09-30T03:50:00+00:00")).all()
