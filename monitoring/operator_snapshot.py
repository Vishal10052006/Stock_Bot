"""Authoritative operator snapshot writer for the real-money manual-review surface.

This module adapts an already-produced live decision into one atomic JSON
snapshot. It does not calculate trading decisions or submit broker orders.
The BUY/SELL action remains manual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json
import os

import pandas as pd

from v1_signal import build_v1_signal_from_decision


def _probabilities(prediction: Any) -> dict[str, float]:
    table = getattr(prediction, "probabilities", None)
    if table is None or not hasattr(table, "iloc") or len(table) != 1:
        raise ValueError("prediction probabilities must contain exactly one row")
    row = table.iloc[0]
    values = {
        "LONG_SUCCESS": float(row["LONG_SUCCESS"]),
        "SHORT_SUCCESS": float(row["SHORT_SUCCESS"]),
        "NO_EDGE": float(row["NO_EDGE"]),
    }
    if any(value < 0.0 or value > 1.0 for value in values.values()):
        raise ValueError("prediction probabilities must lie in [0, 1]")
    if not abs(sum(values.values()) - 1.0) <= 1e-6:
        raise ValueError("prediction probabilities must sum to 1")
    return values


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(slots=True)
class OperatorSnapshotWriter:
    """Persist the latest real-market manual-review decision atomically."""

    path: Path
    symbol: str
    benchmark_symbol: str
    model_version: str
    calibration_version: str | None
    data_version: str
    feature_version: str
    initial_equity: float | None = None
    require_live_account_context: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)
    prediction_count: int = 0
    signal_count: int = 0
    fill_count: int = 0

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not self.benchmark_symbol.strip():
            raise ValueError("benchmark_symbol must not be empty")
        if self.initial_equity is not None and self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive when supplied")
        if self.require_live_account_context and self.initial_equity is not None:
            raise ValueError("V1 manual-review snapshots cannot accept synthetic initial_equity")

    def write_initial(self) -> None:
        """Write an explicit waiting state before the first live-review candle."""
        self._write(
            {
                "mode": "live_market_manual_review",
                "authority": "OBSERVATION_ONLY",
                "timestamp": None,
                "session": {
                    "symbol": self.symbol.upper(),
                    "benchmark_symbol": self.benchmark_symbol.upper(),
                    "model_version": self.model_version,
                    "calibration_version": self.calibration_version,
                    "data_version": self.data_version,
                    "feature_version": self.feature_version,
                },
                "views": {"scanner": {"status": "NO_DATA", "timestamp": None, "rows": [], "authority": "OBSERVATION_ONLY"}},
                "market": {
                    "status": "WAITING_FOR_MARKET",
                    "symbol": self.symbol.upper(),
                    "benchmark_symbol": self.benchmark_symbol.upper(),
                    "price": None,
                    "decision_time": None,
                },
                "pipeline": self._pipeline("WAITING"),
                "prediction": {"status": "WAITING"},
                "strategy": {"status": "WAITING"},
                "risk": {"status": "STANDBY"},
                "execution": {
                    "mode": "REAL_MONEY_MANUAL_REVIEW",
                    "broker_orders": 0,
                    "automated_execution": False,
                },
                "performance": (
                    {
                        "status": "ACCOUNT_STATE_UNAVAILABLE",
                        "initial_equity": None,
                        "equity": None,
                        "total_return": None,
                    }
                    if self.require_live_account_context
                    else {
                        "status": "PAPER_ACCOUNT_CONFIGURED" if self.initial_equity is not None else "ACCOUNT_STATE_UNAVAILABLE",
                        "initial_equity": self.initial_equity,
                        "equity": self.initial_equity,
                        "total_return": 0.0 if self.initial_equity is not None else None,
                    }
                ),
                "metrics": {
                    "model.prediction_count": 0,
                    "strategy.signal_count": 0,
                    "execution.fill_count": 0,
                },
                "health": self._health("WAITING_FOR_MARKET"),
                "events": [],
                "alerts": [],
                "alert_summary": {"total": 0, "by_severity": {}, "by_code": {}},
            }
        )

    def observe(self, decision: Any, candle: Any, paper_engine: Any | None = None) -> None:
        """Publish one completed canonical live-money manual-review decision."""
        prediction = decision.prediction
        timestamp = pd.Timestamp(prediction.timestamp)
        probabilities = _probabilities(prediction)
        strategy = decision.strategy
        direction = getattr(strategy.direction, "value", strategy.direction)
        if direction != "NO_TRADE":
            self.signal_count += 1
        self.prediction_count += 1

        v1_signal = build_v1_signal_from_decision(
            decision,
            valid_until=timestamp + pd.Timedelta(minutes=5),
            research_context=getattr(decision, "research_context", None),
            market_context=getattr(decision, "market_context", None),
        )

        # Market context is carried by the strategy/analysis boundary when
        # available. The V1 adapter remains presentation-only.
        order_status = (
            "MANUAL_BUY_SELL_REQUIRED"
            if direction != "NO_TRADE" and decision.risk_status == "APPROVED"
            else "NO_MANUAL_ACTION"
        )
        risk_context = getattr(decision, "risk_context", None)
        if self.require_live_account_context and risk_context is None:
            raise ValueError(
                "V1 manual-review snapshots require verified live account context"
            )
        if risk_context is not None:
            performance = {
                "status": "LIVE_ACCOUNT_OBSERVED",
                "available_equity": float(risk_context.available_equity),
                "day_start_equity": float(risk_context.day_start_equity),
                "available_cash": float(risk_context.available_cash),
                "peak_equity": float(risk_context.peak_equity),
                "realized_pnl": float(risk_context.realized_pnl),
                "unrealized_pnl": float(risk_context.unrealized_pnl),
                "gross_exposure": float(risk_context.gross_exposure),
                "open_positions": int(risk_context.open_positions),
                "trades_today": int(risk_context.trades_today),
                "as_of": pd.Timestamp(risk_context.as_of).isoformat(),
                "source": str(risk_context.source),
            }
            equity = None
            realized_pnl = float(risk_context.realized_pnl)
            unrealized_pnl = float(risk_context.unrealized_pnl)
            gross_exposure = float(risk_context.gross_exposure)
            total_return = None
        else:
            performance = {
                "status": "PAPER_ACCOUNT_CONFIGURED" if self.initial_equity is not None else "ACCOUNT_STATE_UNAVAILABLE",
                "initial_equity": self.initial_equity,
                "equity": self.initial_equity,
                "total_return": 0.0 if self.initial_equity is not None else None,
            }
            equity = self.initial_equity
            realized_pnl = 0.0
            unrealized_pnl = 0.0
            gross_exposure = 0.0
            total_return = 0.0 if self.initial_equity is not None else None

        event = {
            "timestamp": timestamp.isoformat(),
            "component": "CANONICAL_PIPELINE",
            "message": (
                f"Prediction={getattr(prediction, 'predicted_class', 'UNKNOWN')} "
                f"Strategy={direction} Risk={decision.risk_status} "
                f"ManualExecution={order_status}"
            ),
        }
        self.events.append(event)
        self.events[:] = self.events[-100:]

        payload = {
            "mode": "live_market_manual_review",
            "authority": "OBSERVATION_ONLY",
            "timestamp": timestamp.isoformat(),
            "session": {
                "symbol": self.symbol.upper(),
                "benchmark_symbol": self.benchmark_symbol.upper(),
                "model_version": getattr(prediction, "model_version", self.model_version),
                "calibration_version": getattr(
                    prediction, "calibration_version", self.calibration_version
                ),
                "data_version": self.data_version,
                "feature_version": getattr(
                    prediction, "feature_version", self.feature_version
                ),
            },
            "views": {
                "scanner": self._scanner_view(decision, candle, probabilities, v1_signal),
                "v1_signal": v1_signal.as_dict(),
            },
            "v1_signal": v1_signal.as_dict(),
            "market": {
                "status": "LIVE_MARKET_OBSERVED",
                "symbol": str(candle.symbol).upper(),
                "benchmark_symbol": self.benchmark_symbol.upper(),
                "price": float(candle.close),
                "decision_time": timestamp.isoformat(),
            },
            "pipeline": self._pipeline("OBSERVED"),
            "prediction": {
                "status": "OBSERVED",
                "predicted_class": getattr(prediction, "predicted_class", None),
                "probabilities": probabilities,
                "model_version": getattr(prediction, "model_version", self.model_version),
                "calibration_version": getattr(
                    prediction, "calibration_version", self.calibration_version
                ),
            },
            "strategy": {
                "status": direction,
                "reason": str(getattr(strategy, "rationale", "")),
                "strategy_version": str(getattr(strategy, "strategy_version", "")),
            },
            "risk": {
                "status": str(decision.risk_status),
                "reason": str(decision.risk_reason),
                "gross_exposure": float(gross_exposure),
            },
            "execution": {
                "mode": "REAL_MONEY_MANUAL_REVIEW",
                "manual_execution_status": "PENDING_MANUAL_BUY_SELL",
                "trade_id": None,
                "broker_orders": 0,
                "automated_execution": False,
            },
            "performance": performance | {
                "equity": None if equity is None else float(equity),
                "realized_pnl": float(realized_pnl),
                "unrealized_pnl": float(unrealized_pnl),
                "gross_exposure": float(gross_exposure),
                "total_return": None if total_return is None else float(total_return),
            },
            "metrics": {
                "model.prediction_count": self.prediction_count,
                "strategy.signal_count": self.signal_count,
                "execution.manual_actions": 0,
            },
            "health": self._health("OBSERVED"),
            "events": list(self.events),
            "alerts": [],
            "alert_summary": {"total": 0, "by_severity": {}, "by_code": {}},
        }
        self._write(payload)


    def _scanner_view(self, decision: Any, candle: Any, probabilities: dict[str, float], v1_signal: Any) -> dict[str, Any]:
        """Expose the latest decision through the existing observation-only scanner view."""
        prediction = decision.prediction
        strategy = decision.strategy
        direction = getattr(strategy.direction, "value", strategy.direction)
        return {
            "status": "READY",
            "timestamp": pd.Timestamp(prediction.timestamp).isoformat(),
            "authority": "OBSERVATION_ONLY",
            "rows": [{
                "timestamp": pd.Timestamp(prediction.timestamp).isoformat(),
                "symbol": str(candle.symbol).upper(),
                "price": float(candle.close),
                "long_success": probabilities["LONG_SUCCESS"],
                "short_success": probabilities["SHORT_SUCCESS"],
                "no_edge": probabilities["NO_EDGE"],
                "predicted_class": getattr(prediction, "predicted_class", None),
                "regime": getattr(strategy, "regime", None),
                "strategy": direction,
                "strategy_reason": str(getattr(strategy, "rationale", "")),
                "risk_status": str(decision.risk_status),
                "risk_reason": str(decision.risk_reason),
                "manual_execution_status": decision.manual_execution_status,
                "trade_id": decision.trade_id,
                "prediction_model_version": getattr(prediction, "model_version", self.model_version),
                "calibration_version": getattr(prediction, "calibration_version", self.calibration_version),
                "feature_version": getattr(prediction, "feature_version", self.feature_version),
                "signal_strength": max(probabilities["LONG_SUCCESS"], probabilities["SHORT_SUCCESS"]) - probabilities["NO_EDGE"],
                "display_signal": v1_signal.signal.value,
                "confidence": v1_signal.confidence,
                "valid_until": v1_signal.valid_until.isoformat(),
                "entry_reference": v1_signal.entry,
                "stop_reference": v1_signal.stop_loss,
                "target_reference": v1_signal.target,
                "risk_reward": v1_signal.risk_reward,
                "v1_signal_id": v1_signal.signal_id,
                "v1_fingerprint": v1_signal.as_dict()["fingerprint"],
                "v1_authority": v1_signal.authority,
                "broker_execution": False,
                "manual_execution": True,
                "authority": "OBSERVATION_ONLY",
            }],
        }

    def _pipeline(self, terminal_state: str) -> dict[str, dict[str, str]]:
        return {
            "research": {"status": terminal_state, "authority": "OBSERVATION"},
            "analysis": {"status": terminal_state, "authority": "OBSERVATION"},
            "market": {"status": terminal_state, "authority": "OBSERVATION"},
            "prediction": {"status": terminal_state, "authority": "OBSERVATION"},
            "strategy": {"status": terminal_state, "authority": "OBSERVATION"},
            "risk": {"status": terminal_state, "authority": "GATE"},
            "execution": {"status": "MANUAL_REAL_MONEY", "authority": "HUMAN_REVIEW"},
        }

    def _health(self, status: str) -> list[dict[str, str]]:
        return [
            {"component": "DATA", "status": status, "message": "Observed from canonical real-market candle."},
            {"component": "FEATURES", "status": status, "message": "Decision-time feature path observed."},
            {"component": "CAUSALITY", "status": "ENFORCED", "message": "Canonical causal boundary enforced."},
            {"component": "RISK", "status": status, "message": "Risk result observed; no dashboard authority."},
            {"component": "EXECUTION", "status": "LOCKED", "message": "Manual BUY/SELL only; broker automation remains disabled."},
            {"component": "MODEL", "status": status, "message": "Prediction output observed."},
        ]

    def _write(self, payload: dict[str, Any]) -> None:
        canonical = _canonical(payload)
        payload["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)


__all__ = ["OperatorSnapshotWriter"]
