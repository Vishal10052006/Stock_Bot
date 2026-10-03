from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from trading.live.upstox_risk_context import (
    LiveDayRiskStateStore,
    LiveRiskContextUnavailable,
    UpstoxManualRiskContextProvider,
    UpstoxReadOnlyAccountClient,
)


class FakeReadOnlyClient:
    def __init__(self, responses):
        self.responses = responses

    def get(self, path, *, headers=None):
        return self.responses[path]

    @staticmethod
    def data(response):
        return response["data"]


def _provider(tmp_path: Path, *, trades=None) -> UpstoxManualRiskContextProvider:
    responses = {
        "/v3/user/get-funds-and-margin": {
            "status": "success",
            "data": {
                "available_to_trade": {
                    "total": 100000.0,
                    "cash_available_to_trade": {
                        "total": 90000.0,
                    },
                }
            },
        },
        "/v2/portfolio/short-term-positions": {
            "status": "success",
            "data": [
                {
                    "trading_symbol": "RELIANCE-EQ",
                    "quantity": 10,
                    "value": 25000.0,
                    "realised": 100.0,
                    "unrealised": -50.0,
                }
            ],
        },
        "/v2/portfolio/long-term-holdings": {
            "status": "success",
            "data": [
                {
                    "trading_symbol": "TCS",
                    "quantity": 5,
                    "last_price": 4000.0,
                    "day_change": 25.0,
                }
            ],
        },
        "/v2/order/trades/get-trades-for-day": {
            "status": "success",
            "data": trades if trades is not None else [],
        },
        "/v2/user/profile": {
            "status": "success",
            "data": {"is_active": True},
        },
        "/v2/user/kill-switch": {
            "status": "success",
            "data": [
                {
                    "segment": "NSE_EQ",
                    "segment_status": "ACTIVE",
                    "kill_switch_enabled": False,
                }
            ],
        },
        "/v2/market/status/NSE": {
            "status": "success",
            "data": {"status": "NORMAL_OPEN"},
        },
    }

    return UpstoxManualRiskContextProvider(
        client=FakeReadOnlyClient(responses),
        day_state=LiveDayRiskStateStore(tmp_path / "risk-day.json"),
        exchange="NSE",
        segment="NSE_EQ",
        timezone_name="Asia/Kolkata",
        max_age_seconds=30.0,
        source="upstox-read-only",
    )


def test_read_only_client_is_get_only() -> None:
    client = UpstoxReadOnlyAccountClient(
        "runtime-token",
        api_base_url="https://api.upstox.com",
        timeout_seconds=5.0,
    )
    assert client._timeout_seconds == 5.0
    assert client._api_base_url == "https://api.upstox.com"


def test_provider_builds_context_from_observed_account_state(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    context = provider(
        pd.Timestamp("2026-10-03T10:00:00+05:30"),
        "RELIANCE",
    )

    assert context.available_equity == 100000.0
    assert context.available_cash == 90000.0
    assert context.day_start_equity == 100000.0
    assert context.realized_pnl == 100.0
    assert context.unrealized_pnl == -25.0
    assert context.open_positions == 1
    assert context.gross_exposure == 45000.0
    assert context.symbol_already_open is True
    assert context.kill_switch_active is False
    assert context.system_ready is True
    assert context.market_data_valid is True


def test_provider_refuses_to_reconstruct_missing_day_start_after_trades(
    tmp_path: Path,
) -> None:
    provider = _provider(
        tmp_path,
        trades=[{"order_id": "ORDER-1", "quantity": 1}],
    )

    with pytest.raises(
        LiveRiskContextUnavailable,
        match="day-start risk state is missing",
    ):
        provider(
            pd.Timestamp("2026-10-03T10:00:00+05:30"),
            "RELIANCE",
        )


def test_day_state_store_contains_no_credentials(tmp_path: Path) -> None:
    store = LiveDayRiskStateStore(tmp_path / "risk-day.json")
    from trading.live.upstox_risk_context import LiveDayRiskState

    state = LiveDayRiskState(
        trading_date="2026-10-03",
        day_start_equity=100000.0,
        peak_equity=100000.0,
    )
    store.save(state)

    raw = json.loads((tmp_path / "risk-day.json").read_text(encoding="utf-8"))
    assert set(raw) == {"trading_date", "day_start_equity", "peak_equity"}
