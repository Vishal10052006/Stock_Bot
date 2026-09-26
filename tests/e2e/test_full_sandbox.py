"""End-to-end sandbox/paper boundary validation.

The scenario exercises the chronological paper session, Strategy -> Risk ->
ExecutionAuthorization -> PaperTradingRuntime path, monitoring evidence, and
the Phase 25 locked broker boundary in one test without live broker I/O.
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from execution.broker_gateway import BrokerIntegrationLocked, LockedBrokerGateway
from execution.adapters.paper import PaperBrokerAdapter
from runtime.paper_session import PaperSession


def risk_row(timestamp: str) -> dict[str, object]:
    return {
        "timestamp": pd.Timestamp(timestamp, tz="UTC"),
        "symbol": "RELIANCE",
        "close": 100.0,
        "atr_14": 2.0,
        "swing_low": 96.0,
        "swing_high": 104.0,
        "support_20": 95.0,
        "resistance_20": 105.0,
        "regime": "TREND_UP",
        "regime_probability": 0.90,
        "vwap_distance_pct": 0.5,
        "rvol_20": 1.4,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }


def test_full_sandbox_paper_path_is_observable_and_fail_closed(tmp_path):
    rows = pd.DataFrame(
        [
            risk_row("2026-09-21 10:00:00"),
            risk_row("2026-09-21 10:05:00"),
        ]
    )

    session = PaperSession.from_path(
        tmp_path / "e2e-paper.jsonl",
        session_id="E2E-SANDBOX-001",
        dataset_version="e2e-test-v1",
        code_version="contract-test",
    )
    session.start(now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc))
    result = session.run(
        rows,
        fill_timestamps={0: pd.Timestamp("2026-09-21 10:00:01", tz="UTC")},
        equity_observations={0: 100_000.0},
        operational_events=1,
    )

    assert result.summary()["live_broker_order_submission"] is False
    assert result.evidence.source_run_id == result.run.run_id
    assert len(result.run.steps) == 2
    assert result.run.orders

    gateway = LockedBrokerGateway(PaperBrokerAdapter())
    order = result.run.orders[0]

    # Paper evidence is complete, but the broker gateway remains locked.
    with pytest.raises(BrokerIntegrationLocked):
        gateway.get_order(order.client_order_id)

    assert gateway.evidence()["broker_network_authority"] is False
