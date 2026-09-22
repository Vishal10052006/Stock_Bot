"""Deterministic interpretation of fundamental financial facts."""
from __future__ import annotations

from math import isfinite
from typing import Any

from intelligence.analysis.fundamentals.contracts import FundamentalSnapshot


def _value(metrics: dict[str, float], *names: str) -> float | None:
    for name in names:
        if name in metrics:
            return metrics[name]
    return None


def _ratio(
    numerator: float | None, denominator: float | None
) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    value = float(numerator) / float(denominator)
    return value if isfinite(value) else None


def analyze_fundamentals(
    snapshot: FundamentalSnapshot | None,
) -> dict[str, Any]:
    """Return structured fundamental context without producing a trade signal."""
    if snapshot is None:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "coverage": 0.0,
            "metrics": {},
            "derived": {},
            "source": None,
            "available_at": None,
        }

    m = dict(snapshot.metrics)
    revenue = _value(m, "revenue", "sales")
    gross_profit = _value(m, "gross_profit")
    operating_income = _value(m, "operating_income", "ebit")
    net_income = _value(m, "net_income", "profit_after_tax", "pat")
    assets = _value(m, "total_assets")
    equity = _value(m, "total_equity", "shareholders_equity")
    debt = _value(m, "total_debt", "debt")
    cash = _value(m, "cash_and_equivalents", "cash")
    current_assets = _value(m, "current_assets")
    current_liabilities = _value(m, "current_liabilities")
    operating_cash_flow = _value(m, "operating_cash_flow", "cfo")
    free_cash_flow = _value(m, "free_cash_flow", "fcf")
    revenue_growth = _value(m, "revenue_growth", "revenue_growth_yoy")
    earnings_growth = _value(m, "earnings_growth", "net_income_growth_yoy")

    derived = {
        "gross_margin": _ratio(gross_profit, revenue),
        "operating_margin": _ratio(operating_income, revenue),
        "net_margin": _ratio(net_income, revenue),
        "roe": _ratio(net_income, equity),
        "roa": _ratio(net_income, assets),
        "debt_equity": _ratio(debt, equity),
        "current_ratio": _ratio(current_assets, current_liabilities),
        "cash_to_debt": _ratio(cash, debt),
        "cfo_margin": _ratio(operating_cash_flow, revenue),
        "fcf_margin": _ratio(free_cash_flow, revenue),
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
    }

    expected = {
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "total_assets",
        "total_equity",
        "total_debt",
        "cash_and_equivalents",
        "operating_cash_flow",
        "free_cash_flow",
    }
    coverage = sum(name in m for name in expected) / len(expected)

    states: list[str] = []
    if derived["roe"] is not None:
        states.append("PROFITABLE" if derived["roe"] > 0 else "LOSS_MAKING")
    if derived["debt_equity"] is not None:
        states.append("LEVERAGE_LOW" if derived["debt_equity"] < 1.0 else "LEVERAGE_HIGH")
    if derived["fcf_margin"] is not None:
        states.append("CASH_GENERATIVE" if derived["fcf_margin"] > 0 else "FCF_NEGATIVE")
    if derived["revenue_growth"] is not None:
        states.append("GROWING" if derived["revenue_growth"] > 0 else "REVENUE_CONTRACTING")
    if derived["earnings_growth"] is not None:
        states.append("EARNINGS_GROWING" if derived["earnings_growth"] > 0 else "EARNINGS_CONTRACTING")

    if not states:
        state = "INSUFFICIENT_DATA"
    elif any(item in states for item in ("LOSS_MAKING", "FCF_NEGATIVE", "REVENUE_CONTRACTING", "EARNINGS_CONTRACTING")):
        state = "MIXED_OR_WEAK"
    elif all(item in states for item in ("PROFITABLE", "CASH_GENERATIVE")):
        state = "PROFITABLE_AND_CASH_GENERATIVE"
    else:
        state = "PARTIAL_POSITIVE"

    return {
        "available": True,
        "state": state,
        "coverage": coverage,
        "metrics": m,
        "derived": derived,
        "source": snapshot.source,
        "source_version": snapshot.source_version,
        "period_end": snapshot.period_end.isoformat(),
        "published_at": snapshot.published_at.isoformat(),
        "available_at": snapshot.available_at.isoformat(),
        "statement_type": snapshot.statement_type,
        "consolidated": snapshot.consolidated,
        "provenance": dict(snapshot.provenance),
    }
