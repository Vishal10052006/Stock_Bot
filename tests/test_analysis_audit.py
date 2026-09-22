"""Production-boundary audit tests for Analysis Bot."""
from __future__ import annotations

import pandas as pd

from intelligence.analysis.audit import audit_analysis_context
from intelligence.analysis.contracts import AnalysisInput
from intelligence.analysis.engine import AnalysisEngine


def test_analysis_audit_passes_canonical_context() -> None:
    context = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="RELIANCE",
            features={"rsi_14": 60.0},
            data_version="market-v1",
            feature_version="features-v1",
        )
    )
    report = audit_analysis_context(context)
    assert report.passed is True
    assert all(check.passed for check in report.checks)


def test_analysis_audit_rejects_trade_order_language() -> None:
    context = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="RELIANCE",
            features={"rsi_14": 60.0},
        )
    )
    unsafe = type(context)(
        timestamp=context.timestamp,
        symbol=context.symbol,
        technical_context=context.technical_context,
        structure_context=context.structure_context,
        volume_context=context.volume_context,
        volatility_context=context.volatility_context,
        market_context=context.market_context,
        sector_context=context.sector_context,
        relative_performance=context.relative_performance,
        research_context=context.research_context,
        feature_vector=context.feature_vector,
        analytical_direction=context.analytical_direction,
        analytical_state=context.analytical_state,
        candidates=("BUY_RELIANCE",),
        quality=context.quality,
        analysis_version=context.analysis_version,
        feature_version=context.feature_version,
        data_version=context.data_version,
        provenance=context.provenance,
        fundamental_context=context.fundamental_context,
        valuation_context=context.valuation_context,
    )
    report = audit_analysis_context(unsafe)
    assert report.passed is False
    assert any(check.name == "no_trade_authority" and not check.passed for check in report.checks)
