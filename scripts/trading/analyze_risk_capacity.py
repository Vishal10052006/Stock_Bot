"""Counterfactual research for Risk sizing vs gross-exposure capacity.

References:
- docs/RISK_ENGINE.md
- docs/EMPIRICAL_PAPER_RUN.md
- Issue #61: signal-starvation investigation

This module never changes the frozen Risk policy. It runs the existing
HistoricalBacktestEngine repeatedly with explicitly supplied hypothetical
RiskConfig values and emits a JSON-safe comparison.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from backtesting.engine import BacktestConfig, HistoricalBacktestEngine
from trading.risk.engine import RiskConfig, RiskEngine


@dataclass(frozen=True)
class Scenario:
    """One explicitly named counterfactual Risk policy."""

    name: str
    max_gross_exposure: float
    allow_resize: bool


def _drawdown(outcomes) -> float:
    """Calculate max percentage drawdown from chronological trade net P&L."""
    equity = 100_000.0
    peak = equity
    max_dd = 0.0
    for outcome in outcomes:
        equity += float(outcome.net_pnl)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return max_dd


def _profit_factor(outcomes) -> float | None:
    """Return finite profit factor, or None when no losing trades exist."""
    wins = sum(float(x.net_pnl) for x in outcomes if float(x.net_pnl) > 0)
    losses = -sum(float(x.net_pnl) for x in outcomes if float(x.net_pnl) < 0)
    return wins / losses if losses else None


def run_scenario(rows: pd.DataFrame, scenario: Scenario) -> dict[str, object]:
    """Replay identical chronological data under one counterfactual policy."""
    risk = RiskEngine(
        RiskConfig(
            max_gross_exposure=scenario.max_gross_exposure,
            allow_resize=scenario.allow_resize,
        )
    )
    result = HistoricalBacktestEngine(
        config=BacktestConfig(),
        risk_engine=risk,
    ).run(rows)

    strategy_signals = sum(
        step.strategy.direction.value in {"LONG", "SHORT"}
        for step in result.steps
    )
    risk_rejections = [
        step for step in result.steps if step.risk.status.value == "REJECTED"
    ]
    gross_rejections = sum(
        any(code.value == "MAX_GROSS_EXPOSURE" for code in step.risk.reason_codes)
        for step in risk_rejections
    )
    reason_counts: dict[str, int] = {}
    for step in risk_rejections:
        for code in step.risk.reason_codes:
            reason_counts[code.value] = reason_counts.get(code.value, 0) + 1

    return {
        "scenario": asdict(scenario),
        "steps": len(result.steps),
        "strategy_signals": int(strategy_signals),
        "risk_rejections": len(risk_rejections),
        "gross_exposure_rejections": int(gross_rejections),
        "paper_fills": len(result.orders),
        "completed_trades": result.completed_trades,
        "net_pnl": float(result.net_pnl),
        "max_drawdown": float(_drawdown(result.outcomes)),
        "profit_factor": _profit_factor(result.outcomes),
        "expectancy": (
            float(result.net_pnl / result.completed_trades)
            if result.completed_trades
            else None
        ),
        "risk_rejection_reasons": dict(sorted(reason_counts.items())),
    }


def main() -> None:
    """Run the counterfactual sweep against an existing causal dataset."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV containing the frozen strategy-ready rows.")
    parser.add_argument("--output", required=True, help="JSON output path.")
    args = parser.parse_args()

    rows = pd.read_csv(args.input)
    scenarios = (
        Scenario("frozen_75_hard_reject", 0.75, False),
        Scenario("hypothetical_85_hard_reject", 0.85, False),
        Scenario("hypothetical_100_hard_reject", 1.00, False),
        Scenario("frozen_75_resize_enabled", 0.75, True),
        Scenario("hypothetical_85_resize_enabled", 0.85, True),
    )

    report = {
        "claim_boundary": (
            "Counterfactual software/replay analysis only. Results depend on the "
            "supplied chronological dataset and do not establish profitability, "
            "robustness, or live-trading readiness."
        ),
        "input": str(Path(args.input)),
        "scenarios": [run_scenario(rows, scenario) for scenario in scenarios],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
