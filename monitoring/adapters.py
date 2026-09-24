"""Adapters from existing STOCK_BOT domains into monitoring telemetry."""

from __future__ import annotations

from typing import Mapping


def prediction_payload(telemetry: object) -> Mapping[str, object]:
    """Convert Phase-9 PredictionTelemetry into a monitoring payload."""
    return {
        "timestamp": telemetry.timestamp.isoformat(),
        "symbol": telemetry.symbol,
        "model_version": telemetry.model_version,
        "feature_version": telemetry.feature_version,
        "long_probability": float(telemetry.long_probability),
        "short_probability": float(telemetry.short_probability),
        "no_edge_probability": float(telemetry.no_edge_probability),
        "predicted_class": telemetry.predicted_class,
        "regime": telemetry.regime,
    }


def decision_payload(decision: object) -> Mapping[str, object]:
    """Convert a TradeDecisionRecord-compatible object."""
    return {
        "trade_id": decision.trade_id,
        "timestamp": decision.timestamp.isoformat(),
        "symbol": decision.symbol,
        "direction": decision.direction,
        "market_regime": decision.market_regime,
        "model_version": decision.model_version,
        "probability": decision.probability,
        "strategy_version": decision.strategy_version,
        "risk_version": decision.risk_version,
        "execution_version": decision.execution_version,
        "failure_reason": decision.failure_reason,
    }


def outcome_payload(outcome: object) -> Mapping[str, object]:
    """Convert a TradeJournalRecord-compatible object."""
    return {
        "journal_id": outcome.journal_id,
        "trade_id": outcome.trade_id,
        "symbol": outcome.symbol,
        "direction": outcome.direction,
        "entry_time": outcome.entry_time.isoformat(),
        "exit_time": outcome.exit_time.isoformat(),
        "gross_pnl": float(outcome.gross_pnl),
        "fees": float(outcome.fees),
        "slippage_cost": float(outcome.slippage_cost),
        "net_pnl": float(outcome.net_pnl),
        "holding_minutes": float(outcome.holding_minutes),
        "mae": float(outcome.mae),
        "mfe": float(outcome.mfe),
    }


def safety_payload(decision: object) -> Mapping[str, object]:
    """Convert an IndependentSafetyGate decision."""
    block = getattr(decision.block, "value", decision.block)
    return {
        "allowed": bool(decision.allowed),
        "block": block,
        "reason": decision.reason,
    }


def reconciliation_payload(report: object) -> Mapping[str, object]:
    """Convert a BrokerReconciler report."""
    status = getattr(report.status, "value", report.status)
    return {
        "status": status,
        "safe": bool(report.safe),
        "mismatches": list(report.mismatches),
    }
