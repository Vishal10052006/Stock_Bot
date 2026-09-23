"""Structural validator for paper-trading evidence required by the frozen specification.

This module validates evidence completeness and internal consistency only. It does
not decide whether paper performance is good enough for live trading.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

import pandas as pd

@dataclass(frozen=True, slots=True)
class PaperEvidenceSnapshot:
    """Immutable paper-trading evidence counters for one frozen evidence period."""

    evidence_version: str
    dataset_version: str
    code_version: str
    signal_count: int
    fill_count: int
    slippage_observation_count: int
    latency_observation_count: int
    false_signal_count: int
    drawdown_observation_count: int
    regime_observation_count: int
    calibration_observation_count: int
    operational_event_count: int
    operational_error_count: int
    stale_event_count: int

    def __post_init__(self) -> None:
        for name in (
            "evidence_version",
            "dataset_version",
            "code_version",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")

        for name in (
            "signal_count",
            "fill_count",
            "slippage_observation_count",
            "latency_observation_count",
            "false_signal_count",
            "drawdown_observation_count",
            "regime_observation_count",
            "calibration_observation_count",
            "operational_event_count",
            "operational_error_count",
            "stale_event_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")

    def canonical_json(self) -> str:
        return json.dumps(
            {
                "evidence_version": self.evidence_version,
                "dataset_version": self.dataset_version,
                "code_version": self.code_version,
                "signal_count": self.signal_count,
                "fill_count": self.fill_count,
                "slippage_observation_count": self.slippage_observation_count,
                "latency_observation_count": self.latency_observation_count,
                "false_signal_count": self.false_signal_count,
                "drawdown_observation_count": self.drawdown_observation_count,
                "regime_observation_count": self.regime_observation_count,
                "calibration_observation_count": self.calibration_observation_count,
                "operational_event_count": self.operational_event_count,
                "operational_error_count": self.operational_error_count,
                "stale_event_count": self.stale_event_count,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperEvidenceReport:
    """Validation result; no profitability or live-readiness conclusion."""

    evidence_fingerprint: str
    valid: bool
    issues: tuple[str, ...]


def validate_paper_evidence(
    snapshot: PaperEvidenceSnapshot,
) -> PaperEvidenceReport:
    """Validate completeness and causal accounting boundaries for paper evidence."""

    if not isinstance(snapshot, PaperEvidenceSnapshot):
        raise TypeError("snapshot must be a PaperEvidenceSnapshot")

    issues: list[str] = []

    required_counts = (
        "signal_count",
        "fill_count",
        "slippage_observation_count",
        "latency_observation_count",
        "drawdown_observation_count",
        "regime_observation_count",
        "calibration_observation_count",
        "operational_event_count",
    )
    for field in required_counts:
        if getattr(snapshot, field) == 0:
            issues.append(f"{field} must contain at least one observation")

    if snapshot.fill_count > snapshot.signal_count:
        issues.append("fill_count cannot exceed signal_count")

    if snapshot.false_signal_count > snapshot.signal_count:
        issues.append("false_signal_count cannot exceed signal_count")

    if snapshot.slippage_observation_count > snapshot.fill_count:
        issues.append("slippage_observation_count cannot exceed fill_count")

    if snapshot.latency_observation_count > snapshot.fill_count:
        issues.append("latency_observation_count cannot exceed fill_count")

    if snapshot.operational_error_count > snapshot.operational_event_count:
        issues.append("operational_error_count cannot exceed operational_event_count")

    if snapshot.stale_event_count > snapshot.operational_event_count:
        issues.append("stale_event_count cannot exceed operational_event_count")

    return PaperEvidenceReport(
        evidence_fingerprint=snapshot.fingerprint,
        valid=not issues,
        issues=tuple(issues),
    )


class PaperEvidenceCollector:
    """Accumulate auditable observations from a chronological paper run.

    The collector records observations only; it does not judge whether the
    resulting paper performance is sufficient for live trading.
    """

    def __init__(
        self,
        *,
        evidence_version: str,
        dataset_version: str,
        code_version: str,
    ) -> None:
        self._identity = (evidence_version, dataset_version, code_version)
        self._signal_count = 0
        self._fill_count = 0
        self._slippage_observation_count = 0
        self._latency_observation_count = 0
        self._false_signal_count = 0
        self._drawdown_observation_count = 0
        self._regime_observation_count = 0
        self._calibration_observation_count = 0
        self._operational_event_count = 0
        self._operational_error_count = 0
        self._stale_event_count = 0
        self._peak_equity: float | None = None

    def record_step(
        self,
        step: object,
        *,
        fill_timestamp: object | None = None,
        false_signal: bool | None = None,
        realized_equity: float | None = None,
        calibration_outcome: float | None = None,
    ) -> None:
        """Record one PaperDecisionStep without importing the paper loop module."""

        strategy = getattr(step, "strategy", None)
        order = getattr(step, "order", None)
        if strategy is None:
            raise TypeError("step must expose a strategy decision")

        if getattr(strategy, "direction", None).value != "NO_TRADE":
            self._signal_count += 1

        if getattr(strategy, "regime", None) is not None:
            self._regime_observation_count += 1

        if order is not None and getattr(order, "status", None).value == "FILLED":
            self._fill_count += 1
            self._slippage_observation_count += 1

            if fill_timestamp is not None:
                decision_time = pd.Timestamp(strategy.timestamp)
                fill_time = pd.Timestamp(fill_timestamp)
                if decision_time.tzinfo is None or fill_time.tzinfo is None:
                    raise ValueError("decision and fill timestamps must be timezone-aware")
                if fill_time < decision_time:
                    raise ValueError("fill timestamp cannot precede decision timestamp")
                self._latency_observation_count += 1

        if false_signal is not None:
            self._false_signal_count += int(bool(false_signal))

        if realized_equity is not None:
            equity = float(realized_equity)
            if not math.isfinite(equity) or equity <= 0:
                raise ValueError("realized_equity must be finite and positive")
            if self._peak_equity is None:
                self._peak_equity = equity
            else:
                self._peak_equity = max(self._peak_equity, equity)
            self._drawdown_observation_count += 1

        if calibration_outcome is not None:
            outcome = float(calibration_outcome)
            if not math.isfinite(outcome) or not 0.0 <= outcome <= 1.0:
                raise ValueError("calibration_outcome must be in [0, 1]")
            probability = getattr(strategy, "prediction_probability", None)
            if probability is None:
                raise ValueError(
                    "calibration outcome requires strategy prediction probability"
                )
            self._calibration_observation_count += 1

    def record_operational_event(
        self,
        *,
        error: bool = False,
        stale: bool = False,
    ) -> None:
        """Record one operational event and its optional error/stale flags."""
        self._operational_event_count += 1
        self._operational_error_count += int(error)
        self._stale_event_count += int(stale)

    def snapshot(self) -> PaperEvidenceSnapshot:
        """Freeze all observations into a deterministic evidence snapshot."""
        evidence_version, dataset_version, code_version = self._identity
        return PaperEvidenceSnapshot(
            evidence_version=evidence_version,
            dataset_version=dataset_version,
            code_version=code_version,
            signal_count=self._signal_count,
            fill_count=self._fill_count,
            slippage_observation_count=self._slippage_observation_count,
            latency_observation_count=self._latency_observation_count,
            false_signal_count=self._false_signal_count,
            drawdown_observation_count=self._drawdown_observation_count,
            regime_observation_count=self._regime_observation_count,
            calibration_observation_count=self._calibration_observation_count,
            operational_event_count=self._operational_event_count,
            operational_error_count=self._operational_error_count,
            stale_event_count=self._stale_event_count,
        )
