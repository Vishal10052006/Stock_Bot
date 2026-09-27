"""Phase 21 Live Signal Engine.

References:
- docs/STRATEGY_ENGINE.md
- docs/FINAL_SYSTEM_AUDIT.md
- trading/risk/pipeline.py
- trading/signals/candidate.py

The engine composes existing Strategy and Risk authorities. It never calls a
broker and never mutates strategy, risk, model, or registry state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from trading.risk.engine import RiskConfig, RiskEngine
from trading.risk.pipeline import evaluate_strategy_candidate_risk
from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import (
    NoTradeReason,
    StrategyConfig,
    StrategyDecision,
    StrategyDirection,
    StrategyInput,
)

from .models import (
    LiveSignal,
    LiveSignalInput,
    LiveSignalStatus,
    SignalNoTradeReason,
)
from .risk_state import LiveRiskState


@dataclass(frozen=True, slots=True)
class SignalFreshnessPolicy:
    """Causal freshness policy for decision-time inputs."""

    max_age_seconds: int = 30

    def __post_init__(self) -> None:
        if self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")


class LiveSignalEngine:
    """Build one deterministic signal from one decision-time market snapshot."""

    def __init__(
        self,
        *,
        strategy_config: StrategyConfig | None = None,
        risk_config: RiskConfig | None = None,
        freshness: SignalFreshnessPolicy | None = None,
        now_provider: Callable[[], pd.Timestamp] | None = None,
    ) -> None:
        self.strategy_engine = StrategyEngine(strategy_config)
        self.risk_engine = RiskEngine(risk_config)
        self.freshness = freshness or SignalFreshnessPolicy()
        self._now_provider = now_provider or (lambda: pd.Timestamp.now(tz="UTC"))

    def build(self, value: LiveSignalInput) -> LiveSignal:
        """Evaluate Strategy then Risk and return an immutable signal."""
        if not isinstance(value, LiveSignalInput):
            raise TypeError("value must be LiveSignalInput")
        if not isinstance(value.risk_state, LiveRiskState):
            raise TypeError("risk_state must be LiveRiskState")

        freshness_reason = self._freshness_reason(value.timestamp)
        if freshness_reason is not None:
            return self._blocked_signal(
                value,
                SignalNoTradeReason.STALE_DATA,
                freshness_reason,
            )

        health_reason = self._health_reason(value.risk_state)
        if health_reason is not None:
            return self._blocked_signal(
                value,
                SignalNoTradeReason.INVALID_INPUT,
                health_reason,
            )

        row = pd.Series(dict(value.decision_features))
        row["timestamp"] = value.timestamp
        row["symbol"] = value.symbol

        strategy_input = StrategyInput(
            timestamp=value.timestamp,
            symbol=value.symbol,
            decision_features=value.decision_features,
            prediction=value.prediction,
            market_context=value.market_context,
            analysis_context=value.analysis_context,
            research_context=value.research_context,
            regime=value.regime,
            regime_probability=value.regime_probability,
            cost_estimate=value.cost_estimate,
            cost_fraction=value.cost_fraction,
            slippage_bps=value.slippage_bps,
            liquidity_available=value.liquidity_available,
            versions=value.versions,
        )

        try:
            strategy, _trace = self.strategy_engine.decide(strategy_input)
        except (TypeError, ValueError) as exc:
            return self._blocked_signal(
                value,
                SignalNoTradeReason.PIPELINE_ERROR,
                f"Strategy validation failed: {exc}",
            )

        risk_assessment = evaluate_strategy_candidate_risk(
            strategy,
            row,
            self.risk_engine,
            available_equity=value.risk_state.available_equity,
            day_start_equity=value.risk_state.day_start_equity,
            realized_pnl=value.risk_state.realized_pnl,
            unrealized_pnl=value.risk_state.unrealized_pnl,
            open_positions=value.risk_state.open_positions,
            trades_today=value.risk_state.trades_today,
            gross_exposure=value.risk_state.gross_exposure,
            symbol_already_open=value.risk_state.symbol_already_open,
            liquidity_available=value.risk_state.liquidity_available,
            kill_switch_active=value.risk_state.kill_switch_active,
            risk_enabled=value.risk_state.system_ready,
        )

        risk = risk_assessment.decision
        actionable = (
            strategy.direction is not StrategyDirection.NO_TRADE
            and risk.status is RiskDecisionStatus.APPROVED
            and risk_assessment.position_size is not None
            and risk_assessment.position_size > 0
        )

        status = (
            LiveSignalStatus.ACTIONABLE
            if actionable
            else LiveSignalStatus.NO_TRADE
        )

        reason = None
        if strategy.direction is StrategyDirection.NO_TRADE:
            reason = SignalNoTradeReason.STRATEGY_REJECTED
        elif risk.status is RiskDecisionStatus.REJECTED:
            reason = SignalNoTradeReason.RISK_REJECTED

        signal_id = LiveSignal.deterministic_id(
            timestamp=value.timestamp,
            symbol=value.symbol,
            strategy_version=strategy.strategy_version,
            prediction_model_version=strategy.prediction_model_version,
            feature_version=strategy.feature_version,
            risk_version=risk.risk_version,
        )

        return LiveSignal(
            signal_id=signal_id,
            timestamp=value.timestamp,
            symbol=value.symbol,
            status=status,
            direction=strategy.direction,
            strategy=strategy,
            risk=risk,
            entry_price=risk_assessment.entry_price,
            stop_price=risk_assessment.stop_price,
            target_price=risk_assessment.target_price,
            position_size=risk_assessment.position_size if actionable else None,
            rationale=strategy.rationale,
            no_trade_reason=reason,
            risk_reason=risk.reason,
            provenance={
                "feature_version": strategy.feature_version or "",
                "analysis_version": strategy.analysis_version or "",
                "market_version": strategy.market_version or "",
                "prediction_model_version": strategy.prediction_model_version or "",
                "strategy_version": strategy.strategy_version,
                "risk_version": risk.risk_version,
            },
        )

    def _freshness_reason(self, timestamp: pd.Timestamp) -> str | None:
        """Return a deterministic freshness failure without throwing."""
        now = pd.Timestamp(self._now_provider())
        timestamp = pd.Timestamp(timestamp)
        if now.tzinfo is None:
            return "now_provider must return a timezone-aware timestamp"
        if timestamp.tzinfo is None:
            return "live signal timestamp must be timezone-aware"

        age = (now - timestamp).total_seconds()
        if age < 0:
            return "live signal timestamp cannot be from the future"
        if age > self.freshness.max_age_seconds:
            return (
                "live signal input is stale: "
                f"age={age:.3f}s limit={self.freshness.max_age_seconds}s"
            )
        return None

    @staticmethod
    def _health_reason(state: LiveRiskState) -> str | None:
        """Fail closed on independent system-health boundaries."""
        if not state.system_ready:
            return "system is not ready"
        if not state.market_data_valid:
            return "market data is invalid or unavailable"
        if state.kill_switch_active:
            return "kill switch is active"
        return None

    def _blocked_signal(
        self,
        value: LiveSignalInput,
        reason: SignalNoTradeReason,
        message: str,
    ) -> LiveSignal:
        """Create an auditable NO_TRADE result without entering Strategy/Risk."""
        strategy = StrategyDecision(
            timestamp=value.timestamp,
            symbol=value.symbol,
            direction=StrategyDirection.NO_TRADE,
            strategy_version=self.strategy_engine.config.strategy_version,
            rationale=message,
            primary_reason=(
                NoTradeReason.STALE_PREDICTION
                if reason is SignalNoTradeReason.STALE_DATA
                else NoTradeReason.INVALID_INPUT
            ),
            feature_version=value.versions.get("feature"),
        )
        risk = RiskDecision(
            timestamp=value.timestamp,
            symbol=value.symbol,
            status=RiskDecisionStatus.REJECTED,
            strategy_direction=StrategyDirection.NO_TRADE,
            reason=message,
            risk_version=self.risk_engine.config.risk_version,
        )
        signal_id = LiveSignal.deterministic_id(
            timestamp=value.timestamp,
            symbol=value.symbol,
            strategy_version=strategy.strategy_version,
            prediction_model_version=None,
            feature_version=value.versions.get("feature"),
            risk_version=risk.risk_version,
        )
        return LiveSignal(
            signal_id=signal_id,
            timestamp=value.timestamp,
            symbol=value.symbol,
            status=LiveSignalStatus.NO_TRADE,
            direction=StrategyDirection.NO_TRADE,
            strategy=strategy,
            risk=risk,
            no_trade_reason=reason,
            rationale=message,
            risk_reason=message,
            provenance={
                "feature_version": value.versions.get("feature", ""),
                "strategy_version": strategy.strategy_version,
                "risk_version": risk.risk_version,
            },
        )
