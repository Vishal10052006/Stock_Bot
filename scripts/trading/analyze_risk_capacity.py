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
import hashlib
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


REQUIRED_COLUMNS = (
    "timestamp",
    "symbol",
    "close",
    "regime",
    "regime_probability",
    "vwap_distance_pct",
    "rvol_20",
    "higher_high",
    "higher_low",
    "lower_low",
    "lower_high",
)


def _sha256_file(path: Path) -> str:
    """Return the exact byte-level SHA-256 used by the paper freeze manifest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_manifest(path: Path, manifest_path: Path) -> dict[str, object]:
    """Fail closed unless the supplied artifact matches its frozen manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_version = manifest.get("dataset_version")
    if not dataset_version:
        raise ValueError("paper dataset manifest is missing dataset_version")

    artifact = manifest.get("artifact", {})
    expected_sha = artifact.get("sha256")
    if not expected_sha:
        raise ValueError("paper dataset manifest is missing artifact.sha256")

    actual_sha = _sha256_file(path)
    if actual_sha != expected_sha:
        raise ValueError(
            "paper dataset SHA-256 does not match the freeze manifest: "
            f"expected {expected_sha}, got {actual_sha}"
        )
    return manifest


def _manifest_provenance(
    manifest: dict[str, object] | None,
) -> dict[str, object] | None:
    """Return frozen dataset identity needed to reproduce a report."""
    if manifest is None:
        return None

    artifact = manifest.get("artifact", {})
    if not isinstance(artifact, dict):
        raise ValueError("paper dataset manifest has an invalid artifact section")

    return {
        "manifest_version": manifest.get("manifest_version"),
        "dataset_version": manifest.get("dataset_version"),
        "sha256": artifact.get("sha256"),
        "rows": artifact.get("rows"),
        "symbols": artifact.get("symbols"),
        "period_start": artifact.get("period_start"),
        "period_end": artifact.get("period_end"),
    }


def _load_input(path: Path, manifest_path: Path | None = None) -> pd.DataFrame:
    """Load the strategy-ready artifact while preserving candidate inputs."""
    if manifest_path is not None:
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        _verify_manifest(path, manifest_path)

    if path.suffix.lower() == ".parquet":
        rows = pd.read_parquet(path)
    elif path.suffix.lower() in {".csv", ".txt"}:
        rows = pd.read_csv(path)
    else:
        raise ValueError(
            "input must be a .csv or .parquet strategy-ready artifact"
        )

    missing = sorted(set(REQUIRED_COLUMNS).difference(rows.columns))
    if missing:
        raise ValueError(
            "strategy-ready input is missing required columns: "
            f"{missing}"
        )

    # Preserve all decision-time columns supplied by the frozen artifact.
    # HistoricalBacktestEngine -> candidate construction requires fields such
    # as atr_14/support_20/resistance_20/swing levels when they are present.
    # Selecting only REQUIRED_COLUMNS here silently stripped those fields and
    # converted candidate-construction failures into GENERIC_REJECT results.
    return rows.copy()


def _drawdown(outcomes, *, starting_equity: float) -> float:
    """Calculate max percentage drawdown from chronological trade net P&L."""
    equity = float(starting_equity)
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


def run_scenario(
    rows: pd.DataFrame,
    scenario: Scenario,
    *,
    starting_equity: float = 100_000.0,
) -> dict[str, object]:
    """Replay identical chronological data under one counterfactual policy."""
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")

    risk = RiskEngine(
        RiskConfig(
            max_gross_exposure=scenario.max_gross_exposure,
            allow_resize=scenario.allow_resize,
        )
    )
    result = HistoricalBacktestEngine(
        config=BacktestConfig(starting_equity=starting_equity),
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
        step.risk.reason_code.value == "MAX_GROSS_EXPOSURE"
        for step in risk_rejections
    )
    reason_counts: dict[str, int] = {}
    for step in risk_rejections:
        code = step.risk.reason_code.value
        reason_counts[code] = reason_counts.get(code, 0) + 1

    return {
        "scenario": asdict(scenario),
        "steps": len(result.steps),
        "strategy_signals": int(strategy_signals),
        "risk_rejections": len(risk_rejections),
        "gross_exposure_rejections": int(gross_rejections),
        "paper_fills": len(result.orders),
        "completed_trades": result.completed_trades,
        "net_pnl": float(result.net_pnl),
        "max_drawdown": float(
            _drawdown(result.outcomes, starting_equity=starting_equity)
        ),
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
    parser = argparse.ArgumentParser(
        description="Analyze Risk capacity without changing frozen Risk policy."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="CSV or Parquet containing the frozen strategy-ready rows.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="JSON output path.",
    )
    parser.add_argument(
        "--manifest",
        help=(
            "Optional EMP-02 paper dataset manifest. When supplied, the input "
            "SHA-256 must match the frozen artifact before replay."
        ),
    )
    parser.add_argument(
        "--starting-equity",
        type=float,
        default=100_000.0,
        help="Backtest starting equity; default: 100000.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    manifest_path = Path(args.manifest) if args.manifest else None

    # Verify once here so the emitted report records the exact frozen identity
    # that was actually used for the counterfactual replay.
    verified_manifest = (
        _verify_manifest(input_path, manifest_path)
        if manifest_path is not None
        else None
    )
    rows = _load_input(input_path)

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
        "input": {
            "path": str(input_path),
            "manifest": str(manifest_path) if manifest_path else None,
            "provenance": _manifest_provenance(verified_manifest),
        },
        "starting_equity": float(args.starting_equity),
        "scenarios": [
            run_scenario(
                rows,
                scenario,
                starting_equity=args.starting_equity,
            )
            for scenario in scenarios
        ],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
