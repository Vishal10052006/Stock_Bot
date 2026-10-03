"""Tests for the canonical Version-1 human-review signal contract."""

from __future__ import annotations

import pandas as pd
import pytest

from live_signal import LiveRiskState, LiveSignalEngine, LiveSignalInput, SignalFreshnessPolicy
from v1_signal import V1Evidence, V1Signal, build_v1_signal


TIMESTAMP = pd.Timestamp("2026-09-27T09:30:00Z")


def _live_signal():
    features = {
        "close": 100.0,
        "atr_14": 2.0,
        "swing_low": 95.0,
        "support_20": 95.0,
        "vwap_distance_pct": 0.02,
        "rvol_20": 1.5,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }
    value = LiveSignalInput(
        timestamp=TIMESTAMP,
        symbol="ITC",
        decision_features=features,
        risk_state=LiveRiskState(
            available_equity=100_000.0,
            day_start_equity=100_000.0,
        ),
        regime="TREND_UP",
        regime_probability=0.90,
        versions={
            "feature": "feature-v1",
            "analysis": "analysis-v1",
            "market": "market-v1",
            "research": "research-v1",
        },
    )
    return LiveSignalEngine(
        freshness=SignalFreshnessPolicy(max_age_seconds=30),
        now_provider=lambda: pd.Timestamp("2026-09-27T09:30:05Z"),
    ).build(value)


def test_builds_buy_contract_with_trade_levels_and_rr():
    contract = build_v1_signal(
        _live_signal(),
        valid_until=pd.Timestamp("2026-09-27T09:35:00Z"),
        technical_evidence=(
            V1Evidence(
                category="technical",
                source="indicator-engine",
                timestamp=TIMESTAMP,
                status="SUPPORTING",
                reason="Trend structure and volume conditions passed.",
            ),
        ),
        risk_conditions=("Risk gate approved the candidate.",),
    )

    assert contract.signal is V1Signal.BUY
    assert contract.entry == 100.0
    assert contract.stop_loss is not None
    assert contract.target is not None
    assert contract.risk_reward is not None
    assert contract.risk_reward > 0
    assert contract.authority == "HUMAN_REVIEW_ONLY"
    assert contract.broker_execution is False

    payload = contract.as_dict()
    assert payload["signal"] == "BUY"
    assert payload["valid_until"] == "2026-09-27T09:35:00+00:00"
    assert payload["technical_evidence"][0]["source"] == "indicator-engine"
    assert payload["fingerprint"]


def test_no_trade_becomes_wait():
    live = _live_signal()
    # A stale input is guaranteed to fail closed before strategy execution.
    stale = LiveSignalEngine(
        freshness=SignalFreshnessPolicy(max_age_seconds=30),
        now_provider=lambda: pd.Timestamp("2026-09-27T10:00:00Z"),
    ).build(
        LiveSignalInput(
            timestamp=live.timestamp,
            symbol=live.symbol,
            decision_features={"close": 100.0},
            risk_state=LiveRiskState(
                available_equity=100_000.0,
                day_start_equity=100_000.0,
            ),
            versions={"feature": "feature-v1"},
        )
    )
    contract = build_v1_signal(
        stale,
        valid_until=pd.Timestamp("2026-09-27T10:05:00Z"),
    )
    assert contract.signal is V1Signal.WAIT


def test_future_evidence_is_rejected():
    with pytest.raises(ValueError, match="future V1 evidence"):
        build_v1_signal(
            _live_signal(),
            valid_until=pd.Timestamp("2026-09-27T09:35:00Z"),
            market_sector_evidence=(
                V1Evidence(
                    category="market",
                    source="nifty",
                    timestamp=pd.Timestamp("2026-09-27T09:31:00Z"),
                    status="SUPPORTING",
                    reason="Future evidence must not enter a past decision.",
                ),
            ),
        )


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_v1_signal(
            _live_signal(),
            valid_until=pd.Timestamp("2026-09-27 09:35:00"),
        )


def test_contract_cannot_enable_broker_execution():
    live = _live_signal()
    with pytest.raises(ValueError, match="broker execution"):
        from v1_signal.contracts import V1SignalContract

        V1SignalContract(
            signal_id=live.signal_id,
            timestamp=live.timestamp,
            symbol=live.symbol,
            signal=V1Signal.BUY,
            entry=100.0,
            stop_loss=98.0,
            target=104.0,
            risk_reward=2.0,
            confidence=0.8,
            prediction_evidence={},
            valid_until=pd.Timestamp("2026-09-27T09:35:00Z"),
            broker_execution=True,
        )
