"""Final empirical completion gate for the STOCK_BOT Monitoring Engine.

M-20..M-24 are evidence/completion gates layered on top of the completed
M-1..M-19 monitoring implementation. They do not add trading authority,
change Risk/Strategy behavior, or manufacture missing observations.

The validator is intentionally conservative:
- zero calibration observations are valid when the baseline emits no probabilities;
- zero false-signal outcomes are reported as unobserved, not fabricated;
- structural completion is never interpreted as profitability or live readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MonitoringCompletionGate:
    name: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class MonitoringCompletionReport:
    status: str
    gates: tuple[MonitoringCompletionGate, ...]
    source_report: str
    fingerprint: str

    @property
    def valid(self) -> bool:
        return all(gate.passed for gate in self.gates)


def _pick(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        for name in names:
            if name in evidence:
                return evidence[name]
    return None


def _non_negative_int(value: Any, name: str, gates: list[MonitoringCompletionGate]) -> None:
    ok = isinstance(value, int) and not isinstance(value, bool) and value >= 0
    gates.append(
        MonitoringCompletionGate(
            f"field.{name}",
            ok,
            f"{name}={value!r}" if ok else f"{name} must be a non-negative integer",
        )
    )


def validate_monitoring_report(
    payload: dict[str, Any],
    *,
    source_report: str = "<memory>",
) -> MonitoringCompletionReport:
    gates: list[MonitoringCompletionGate] = []

    status = _pick(payload, "status")
    gates.append(
        MonitoringCompletionGate(
            "M-20 evidence status",
            status == "EVIDENCE_VALIDATED",
            "empirical evidence is validated"
            if status == "EVIDENCE_VALIDATED"
            else f"status must be EVIDENCE_VALIDATED, got {status!r}",
        )
    )

    fingerprint = _pick(payload, "evidence_fingerprint", "fingerprint")
    fingerprint_ok = (
        isinstance(fingerprint, str)
        and len(fingerprint) == 64
        and all(c in "0123456789abcdef" for c in fingerprint.lower())
    )
    gates.append(
        MonitoringCompletionGate(
            "M-20 evidence identity",
            fingerprint_ok,
            "64-character SHA-256 evidence fingerprint present"
            if fingerprint_ok
            else "missing or invalid evidence fingerprint",
        )
    )

    source_run_id = _pick(payload, "source_run_id", "run_id")
    gates.append(
        MonitoringCompletionGate(
            "M-21 chronological run identity",
            isinstance(source_run_id, str) and bool(source_run_id.strip()),
            "source run identity present"
            if isinstance(source_run_id, str) and source_run_id.strip()
            else "source run identity is missing",
        )
    )

    steps = _pick(payload, "steps", "step_count", "run_steps")
    _non_negative_int(steps, "steps", gates)
    gates.append(
        MonitoringCompletionGate(
            "M-21 chronological observation period",
            isinstance(steps, int) and steps > 0,
            "one or more chronological observations are represented"
            if isinstance(steps, int) and steps > 0
            else "chronological run must contain at least one step",
        )
    )

    signal_count = _pick(payload, "signal_count", "signals")
    fill_count = _pick(payload, "fill_count", "fills", "order_fill_count")
    latency_count = _pick(payload, "latency_observation_count", "latency_observations")
    drawdown_count = _pick(payload, "drawdown_observation_count", "drawdown_observations")
    operational_count = _pick(payload, "operational_event_count", "operational_events")
    stale_count = _pick(payload, "stale_event_count", "stale_events")
    calibration_count = _pick(payload, "calibration_observation_count", "calibration_observations")
    false_signal_count = _pick(payload, "false_signal_count", "false_signal_outcomes")

    for name, value in (
        ("signal_count", signal_count),
        ("fill_count", fill_count),
        ("latency_observation_count", latency_count),
        ("drawdown_observation_count", drawdown_count),
        ("operational_event_count", operational_count),
        ("stale_event_count", stale_count),
        ("calibration_observation_count", calibration_count),
        ("false_signal_count", false_signal_count),
    ):
        _non_negative_int(value, name, gates)

    gates.append(
        MonitoringCompletionGate(
            "M-22 cross-layer coverage",
            all(isinstance(v, int) and v >= 0 for v in (signal_count, fill_count, drawdown_count, operational_count)),
            "strategy, execution, performance and operational counters are present",
        )
    )

    relation_checks = (
        ("fills <= signals", fill_count, signal_count),
        ("latency observations <= fills", latency_count, fill_count),
        ("stale events <= operational events", stale_count, operational_count),
        ("drawdown observations <= steps", drawdown_count, steps),
        ("operational events <= steps", operational_count, steps),
    )
    for name, left, right in relation_checks:
        ok = isinstance(left, int) and isinstance(right, int) and left <= right
        gates.append(
            MonitoringCompletionGate(
                f"M-22 {name}",
                ok,
                "constraint satisfied" if ok else f"invalid relationship: {left!r} <= {right!r}",
            )
        )

    calibration_ok = isinstance(calibration_count, int) and calibration_count >= 0
    calibration_note = (
        "calibration is not applicable when the deterministic baseline emits no probabilities"
        if calibration_count == 0
        else "calibration observations are present"
    )
    gates.append(
        MonitoringCompletionGate(
            "M-23 calibration semantics",
            calibration_ok,
            calibration_note if calibration_ok else "invalid calibration observation count",
        )
    )

    false_signal_ok = isinstance(false_signal_count, int) and false_signal_count >= 0
    gates.append(
        MonitoringCompletionGate(
            "M-23 failure observability",
            false_signal_ok,
            "false-signal outcome count is explicitly represented; zero means unobserved, not zero-loss performance"
            if false_signal_ok
            else "invalid false-signal outcome count",
        )
    )

    gates.append(
        MonitoringCompletionGate(
            "M-24 operational observability",
            isinstance(operational_count, int) and operational_count > 0,
            "operational observations exist for the empirical run"
            if isinstance(operational_count, int) and operational_count > 0
            else "no operational observations were recorded",
        )
    )

    gates.append(
        MonitoringCompletionGate(
            "M-24 no fabricated evidence",
            isinstance(stale_count, int) and isinstance(calibration_count, int),
            "staleness and calibration are represented explicitly, including zero/N/A cases",
        )
    )

    return MonitoringCompletionReport(
        status="COMPLETE" if all(g.passed for g in gates) else "INCOMPLETE",
        gates=tuple(gates),
        source_report=source_report,
        fingerprint=str(fingerprint or ""),
    )


def load_and_validate(path: str | Path) -> MonitoringCompletionReport:
    report_path = Path(path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("monitoring empirical report must contain a JSON object")
    return validate_monitoring_report(payload, source_report=str(report_path))


def render_report(report: MonitoringCompletionReport) -> str:
    lines = [
        "STOCK_BOT MONITORING COMPLETION GATE",
        f"status: {report.status}",
        f"source: {report.source_report}",
        f"fingerprint: {report.fingerprint}",
        "",
    ]
    for gate in report.gates:
        lines.append(f"[{'PASS' if gate.passed else 'FAIL'}] {gate.name}: {gate.message}")
    lines.extend(
        [
            "",
            "Interpretation:",
            "- COMPLETE means the monitoring evidence/completion contract passed.",
            "- It does not prove profitability, predictive edge, or live-trading readiness.",
            "- Monitoring remains observational and cannot authorize, reject, size, execute, or promote.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate final empirical Monitoring Engine completion.")
    parser.add_argument(
        "--report",
        default="data/paper/empirical_paper_report_v3.json",
        help="Empirical paper report JSON",
    )
    args = parser.parse_args()

    report = load_and_validate(args.report)
    print(render_report(report))
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
