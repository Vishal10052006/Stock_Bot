"""Analyze one deterministic empirical paper run for failure and execution coverage.

This report is descriptive only. It does not score the strategy, optimize thresholds,
or authorize trading. It reruns the frozen strategy-ready dataset through the
authoritative PaperDecisionLoop and summarizes observed decision/risk/execution
outcomes plus the runtime equity path.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.trading.run_empirical_paper import _load_rows
from trading.paper.decision_loop import PaperDecisionLoop


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def analyze(rows: pd.DataFrame) -> dict[str, Any]:
    run = PaperDecisionLoop().run(rows)

    risk_statuses = [step.risk.status.value for step in run.steps]
    authorization_statuses = [step.authorization.status.value for step in run.steps]

    signal_steps = [
        step for step in run.steps
        if step.strategy.direction.value != "NO_TRADE"
    ]
    order_steps = [step for step in run.steps if step.order is not None]
    filled_steps = [
        step for step in order_steps
        if step.order.status.value == "FILLED"
    ]

    rejection_reasons = Counter(
        step.risk.reason
        for step in signal_steps
        if step.risk.status.value != "APPROVED"
    )

    signal_symbols = Counter(step.strategy.symbol for step in signal_steps)
    signal_regimes = Counter(step.strategy.regime for step in signal_steps)

    exposure_rejections = [
        step for step in signal_steps
        if (
            step.risk.reason == "Maximum gross exposure would be exceeded."
            and step.risk_assessment is not None
            and step.risk_assessment.gross_exposure_before is not None
            and step.risk_assessment.gross_exposure_limit is not None
            and step.risk_assessment.gross_exposure_after is not None
        )
    ]
    before = [
        float(step.risk_assessment.gross_exposure_before) / float(step.risk_assessment.gross_exposure_limit)
        for step in exposure_rejections
    ]
    after = [
        float(step.risk_assessment.gross_exposure_after) / float(step.risk_assessment.gross_exposure_limit)
        for step in exposure_rejections
    ]
    excess = [
        float(step.risk_assessment.gross_exposure_after) - float(step.risk_assessment.gross_exposure_limit)
        for step in exposure_rejections
    ]
    exposure_constrained_quantities = []
    quantity_reduction_ratios = []
    exposure_constrained_risk = []
    risk_utilization_ratios = []
    zero_exposure_constrained_risk = []
    zero_exposure_risk_utilization_ratios = []
    zero_exposure_incompatible = 0
    for step in exposure_rejections:
        assessment = step.risk_assessment
        if (
            assessment.entry_price is None
            or assessment.position_size is None
            or assessment.gross_exposure_before is None
            or assessment.gross_exposure_limit is None
            or assessment.risk_budget is None
        ):
            continue
        exposure_limit = float(assessment.gross_exposure_limit)
        remaining = max(
            0.0,
            exposure_limit - float(assessment.gross_exposure_before),
        )
        max_quantity = int(remaining // float(assessment.entry_price))
        zero_exposure_quantity = int(
            exposure_limit // float(assessment.entry_price)
        )
        exposure_constrained_quantities.append(max_quantity)
        if float(assessment.position_size) > 0:
            quantity_reduction_ratios.append(
                max_quantity / float(assessment.position_size)
            )
        constrained_risk = (
            max_quantity * float(assessment.stop_distance)
            if assessment.stop_distance is not None
            else None
        )
        zero_exposure_risk = (
            zero_exposure_quantity * float(assessment.stop_distance)
            if assessment.stop_distance is not None
            else None
        )
        if constrained_risk is not None:
            exposure_constrained_risk.append(constrained_risk)
            if float(assessment.risk_budget) > 0:
                risk_utilization_ratios.append(
                    constrained_risk / float(assessment.risk_budget)
                )
        if zero_exposure_risk is not None:
            zero_exposure_constrained_risk.append(zero_exposure_risk)
            if float(assessment.risk_budget) > 0:
                zero_exposure_risk_utilization_ratios.append(
                    zero_exposure_risk / float(assessment.risk_budget)
                )
        if float(assessment.proposed_value) > float(assessment.gross_exposure_limit):
            zero_exposure_incompatible += 1

    exposure_summary = {
        "rejections": len(exposure_rejections),
        "utilization_before": {
            "min": min(before) if before else None,
            "median": float(pd.Series(before).median()) if before else None,
            "max": max(before) if before else None,
        },
        "utilization_after": {
            "min": min(after) if after else None,
            "median": float(pd.Series(after).median()) if after else None,
            "max": max(after) if after else None,
        },
        "excess_exposure": {
            "min": min(excess) if excess else None,
            "median": float(pd.Series(excess).median()) if excess else None,
            "max": max(excess) if excess else None,
        },
        "by_symbol": dict(
            sorted(Counter(step.risk.symbol for step in exposure_rejections).items())
        ),
        "sizing": {
            "risk_budget": [
                float(step.risk_assessment.risk_budget)
                for step in exposure_rejections
                if step.risk_assessment.risk_budget is not None
            ],
            "stop_distance": [
                float(step.risk_assessment.stop_distance)
                for step in exposure_rejections
                if step.risk_assessment.stop_distance is not None
            ],
            "position_size": [
                float(step.risk_assessment.position_size)
                for step in exposure_rejections
                if step.risk_assessment.position_size is not None
            ],
            "proposed_value": [
                float(step.risk_assessment.proposed_value)
                for step in exposure_rejections
                if step.risk_assessment.proposed_value is not None
            ],
        },
        "exposure_constraint": {
            "zero_exposure_incompatible_count": zero_exposure_incompatible,
            "exposure_constrained_quantity": exposure_constrained_quantities,
            "risk_first_to_exposure_quantity_ratio": quantity_reduction_ratios,
            "exposure_constrained_risk": exposure_constrained_risk,
            "exposure_constrained_risk_to_budget_ratio": risk_utilization_ratios,
            "zero_exposure_constrained_risk": zero_exposure_constrained_risk,
            "zero_exposure_risk_to_budget_ratio": zero_exposure_risk_utilization_ratios,
        },
    }

    fill_symbols = Counter(step.order.symbol for step in filled_steps)
    fill_directions = Counter(step.order.direction.value for step in filled_steps)

    equities = list(run.equity_observations)
    equity_summary: dict[str, Any]
    if equities:
        peak = equities[0]
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        for equity in equities:
            peak = max(peak, equity)
            drawdown = peak - equity
            drawdown_pct = drawdown / peak if peak else 0.0
            max_drawdown = max(max_drawdown, drawdown)
            max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

        equity_summary = {
            "observations": len(equities),
            "start": equities[0],
            "end": equities[-1],
            "min": min(equities),
            "max": max(equities),
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown_pct,
        }
    else:
        equity_summary = {"observations": 0}

    return {
        "claim_boundary": (
            "Descriptive empirical paper-run failure/execution analysis only; "
            "no profitability, ranking, optimization, or live-readiness conclusion."
        ),
        "run": {
            "run_id": run.run_id,
            "steps": len(run.steps),
            "signals": len(signal_steps),
            "orders": len(order_steps),
            "filled_orders": len(filled_steps),
            "no_trade_steps": len(run.steps) - len(signal_steps),
        },
        "risk": {
            "status_counts": _count(risk_statuses),
            "signal_rejection_reasons": [
                {"reason": reason, "count": count}
                for reason, count in rejection_reasons.most_common()
            ],
        },
        "authorization": {
            "status_counts": _count(authorization_statuses),
        },
        "signals": {
            "by_symbol": dict(sorted(signal_symbols.items())),
            "by_regime": dict(sorted(signal_regimes.items())),
        },
        "fills": {
            "by_symbol": dict(sorted(fill_symbols.items())),
            "by_direction": dict(sorted(fill_directions.items())),
        },
        "exposure_diagnostics": exposure_summary,
        "equity": equity_summary,
        "observation_boundary": {
            "latency": (
                "deterministic_paper_fill_timestamp"
                if filled_steps
                else "not_observed"
            ),
            "equity": (
                "paper_runtime_account_snapshot"
                if equities
                else "not_observed"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dataset-version", required=True)
    args = parser.parse_args()

    source = Path(args.input)
    rows = _load_rows(source)
    report = analyze(rows)
    report["dataset"] = {
        "path": str(source),
        "sha256": _sha256(source),
        "dataset_version": args.dataset_version,
        "rows": len(rows),
        "period_start": rows["timestamp"].min().isoformat(),
        "period_end": rows["timestamp"].max().isoformat(),
        "symbols": sorted(rows["symbol"].unique().tolist()),
    }

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("=" * 72)
    print("STOCK BOT — EMPIRICAL PAPER FAILURE ANALYSIS")
    print("=" * 72)
    print(f"Rows                 : {len(rows):,}")
    print(f"Signals              : {report['run']['signals']:,}")
    print(f"Filled orders        : {report['run']['filled_orders']:,}")
    print(f"Risk statuses        : {report['risk']['status_counts']}")
    print(f"Max drawdown         : {report['equity'].get('max_drawdown', 0.0):.2f}")
    print(
        "Max drawdown %       : "
        f"{report['equity'].get('max_drawdown_pct', 0.0) * 100:.4f}%"
    )
    print(f"Report               : {target}")
    print("=" * 72)


if __name__ == "__main__":
    main()
