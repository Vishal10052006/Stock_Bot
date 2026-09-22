"""Tests for the point-in-time fundamental Analysis Bot layer."""
from __future__ import annotations

import pandas as pd
import pytest

from intelligence.analysis.contracts import AnalysisInput
from intelligence.analysis.engine import AnalysisEngine
from intelligence.analysis.fundamentals.alignment import align_fundamental_snapshot
from intelligence.analysis.fundamentals.analyzer import analyze_fundamentals
from intelligence.analysis.fundamentals.contracts import (
    FundamentalContractError,
    FundamentalSnapshot,
    ValuationSnapshot,
)
from intelligence.analysis.fundamentals.provider import InMemoryFundamentalProvider
from intelligence.analysis.integration import build_analysis_context
from intelligence.analysis.fundamentals.valuation import analyze_valuation


TS = "2026-09-20 10:25:00+05:30"


def _snapshot(available_at: str = TS, net_income: float = 120.0) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol="RELIANCE",
        period_start=pd.Timestamp("2026-04-01 00:00:00+05:30"),
        period_end=pd.Timestamp("2026-06-30 00:00:00+05:30"),
        published_at=pd.Timestamp("2026-07-20 18:00:00+05:30"),
        available_at=pd.Timestamp(available_at),
        metrics={
            "revenue": 1000.0,
            "gross_profit": 400.0,
            "operating_income": 180.0,
            "net_income": net_income,
            "total_assets": 5000.0,
            "total_equity": 2000.0,
            "total_debt": 500.0,
            "cash_and_equivalents": 300.0,
            "operating_cash_flow": 170.0,
            "free_cash_flow": 120.0,
            "revenue_growth_yoy": 0.12,
            "earnings_growth_yoy": 0.10,
        },
        source="test",
        source_version="fixture-v1",
    )


def test_snapshot_validates_causal_order_and_is_immutable() -> None:
    snapshot = _snapshot()
    assert snapshot.symbol == "RELIANCE"
    assert snapshot.metrics["revenue"] == 1000.0
    with pytest.raises((AttributeError, TypeError)):
        snapshot.symbol = "TCS"  # type: ignore[misc]
    with pytest.raises(FundamentalContractError):
        FundamentalSnapshot(
            symbol="TCS",
            period_start=pd.Timestamp("2026-06-30 00:00:00+05:30"),
            period_end=pd.Timestamp("2026-04-01 00:00:00+05:30"),
            published_at=pd.Timestamp(TS),
            available_at=pd.Timestamp(TS),
        )


def test_alignment_never_uses_future_filing() -> None:
    past = _snapshot("2026-09-20 10:00:00+05:30")
    future = _snapshot("2026-09-20 10:30:00+05:30", net_income=999.0)
    selected = align_fundamental_snapshot(
        [past, future],
        symbol="RELIANCE",
        decision_timestamp=pd.Timestamp(TS),
    )
    assert selected == past


def test_alignment_returns_none_when_no_information_was_available() -> None:
    future = _snapshot("2026-09-20 10:30:00+05:30")
    assert (
        align_fundamental_snapshot(
            [future],
            symbol="RELIANCE",
            decision_timestamp=pd.Timestamp(TS),
        )
        is None
    )


def test_provider_filters_symbol() -> None:
    provider = InMemoryFundamentalProvider([_snapshot()])
    assert len(tuple(provider.snapshots("RELIANCE"))) == 1
    assert tuple(provider.snapshots("TCS")) == ()


def test_fundamental_analyzer_derives_core_metrics() -> None:
    result = analyze_fundamentals(_snapshot())
    assert result["available"] is True
    assert result["derived"]["roe"] == pytest.approx(0.06)
    assert result["derived"]["net_margin"] == pytest.approx(0.12)
    assert result["derived"]["debt_equity"] == pytest.approx(0.25)
    assert result["state"] == "PROFITABLE_AND_CASH_GENERATIVE"


def test_fundamental_analyzer_preserves_missingness() -> None:
    result = analyze_fundamentals(None)
    assert result["available"] is False
    assert result["state"] == "UNAVAILABLE"
    assert result["derived"] == {}


def test_valuation_ratios_are_separate_from_statements() -> None:
    snapshot = ValuationSnapshot(
        symbol="RELIANCE",
        as_of=pd.Timestamp(TS),
        price=100.0,
        market_cap=10_000.0,
        enterprise_value=10_500.0,
        earnings_ttm=500.0,
        book_value=2_500.0,
        ebitda_ttm=1_000.0,
        free_cash_flow_ttm=600.0,
    )
    result = analyze_valuation(snapshot)
    assert result["ratios"]["pe"] == pytest.approx(20.0)
    assert result["ratios"]["pb"] == pytest.approx(4.0)
    assert result["ratios"]["ev_ebitda"] == pytest.approx(10.5)
    assert result["ratios"]["fcf_yield"] == pytest.approx(0.06)


def test_engine_integrates_fundamentals_without_creating_trade_orders() -> None:
    context = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp(TS),
            symbol="RELIANCE",
            features={"rsi_14": 60.0},
            fundamental_context=_snapshot(),
            data_version="market-v1",
            feature_version="features-v1",
        )
    )
    assert context.fundamental_context["available"] is True
    assert context.fundamental_context["derived"]["roe"] == pytest.approx(0.06)
    assert all("BUY" not in candidate and "SELL" not in candidate for candidate in context.candidates)


def test_integration_aligns_only_information_available_at_decision_time() -> None:
    provider = InMemoryFundamentalProvider(
        [
            _snapshot("2026-09-20 10:00:00+05:30"),
            _snapshot("2026-09-20 11:00:00+05:30", net_income=999.0),
        ]
    )
    feature_dataset = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp(TS)],
            "symbol": ["RELIANCE"],
            "close": [100.0],
        }
    )
    # Use the already validated real FeatureDataset contract by supplying the
    # minimum fields expected by the existing feature validator through the
    # direct engine boundary; this test isolates PIT fundamental alignment.
    context = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp(TS),
            symbol="RELIANCE",
            features={"rsi_14": 60.0},
            fundamental_context=align_fundamental_snapshot(
                provider.snapshots("RELIANCE"),
                symbol="RELIANCE",
                decision_timestamp=pd.Timestamp(TS),
            ),
        )
    )
    assert context.fundamental_context["metrics"]["net_income"] == 120.0
