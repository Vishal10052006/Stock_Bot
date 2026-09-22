"""Authoritative quantitative Strategy Engine."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .baseline import evaluate_row
from .models import (\n    BaselineStrategyConfig,\n    NoTradeReason,\n    StrategyConfig,\n    StrategyDecision,\n    StrategyDirection,\n    StrategyInput,\n)
from .policy import prediction_allows_direction, prediction_evidence


@dataclass(frozen=True, slots=True)
class StrategyTrace:
    """Observable decision trace for monitoring and failure analysis."""

    stages: tuple[str, ...]
    failed_reasons: tuple[NoTradeReason, ...]


class StrategyEngine:
    """Canonical quantitative trading decision layer."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()

    @staticmethod
    def coerce_config(
        config: StrategyConfig | BaselineStrategyConfig | None,
    ) -> StrategyConfig:
        """Normalize legacy baseline config to the authoritative engine config."""
        if config is None:
            return StrategyConfig()
        if isinstance(config, StrategyConfig):
            return config
        if isinstance(config, BaselineStrategyConfig):
            return StrategyConfig(baseline=config)
        raise TypeError(
            "strategy config must be StrategyConfig, BaselineStrategyConfig, or None"
        )

    def decide(self, strategy_input: StrategyInput) -> tuple[StrategyDecision, StrategyTrace]:
        """Produce one deterministic TRADE/NO_TRADE decision."""
        self._validate_input(strategy_input)
        stages = ["INPUT_VALIDATION", "CONTEXT_VALIDATION"]

        row = pd.Series(dict(strategy_input.decision_features))
        row["timestamp"] = strategy_input.timestamp
        row["symbol"] = strategy_input.symbol
        row["regime"] = strategy_input.regime
        row["regime_probability"] = strategy_input.regime_probability

        pred_cls, pred_prob, pred_margin, pred_error = prediction_evidence(
            strategy_input.prediction,
            timestamp=strategy_input.timestamp,
            symbol=strategy_input.symbol,
            config=self.config,
        )
        stages.append("PREDICTION_VALIDATION")
        if pred_error is not None:
            return self._reject(strategy_input, pred_error, stages, pred_cls, pred_prob, pred_margin)

        baseline = evaluate_row(row, config=self.config.baseline)
        stages.append("BASELINE_STRATEGY")

        checks = (
            ("REGIME_FILTER", self._regime_reason(strategy_input)),
            (
                "PREDICTION_POLICY",
                prediction_allows_direction(
                    pred_cls,
                    baseline.direction,
                    config=self.config,
                    probability=pred_prob,
                    margin=pred_margin,
                ),
            ),
            ("ANALYSIS_FILTER", self._analysis_reason(strategy_input, baseline.direction)),
            ("LIQUIDITY_FILTER", self._liquidity_reason(strategy_input)),
            ("COST_FILTER", self._cost_reason(strategy_input)),
        )

        for stage, reason in checks:
            if reason is not None:
                return self._reject(
                    strategy_input,
                    reason,
                    stages + [stage],
                    pred_cls,
                    pred_prob,
                    pred_margin,
                    baseline.rationale,
                )

        if baseline.direction is StrategyDirection.NO_TRADE:
            reason = (
                NoTradeReason.REGIME_NOT_ELIGIBLE
                if strategy_input.regime not in self.config.allowed_regimes
                else NoTradeReason.STRATEGY_CONDITION_FAILED
            )
            return self._reject(
                strategy_input,
                reason,
                stages + ["FINAL_DECISION"],
                pred_cls,
                pred_prob,
                pred_margin,
                baseline.rationale,
            )

        decision = StrategyDecision(
            timestamp=strategy_input.timestamp,
            symbol=strategy_input.symbol,
            direction=baseline.direction,
            strategy_version=self.config.strategy_version,
            rationale=baseline.rationale,
            prediction_class=pred_cls,
            prediction_probability=pred_prob,
            prediction_margin=pred_margin,
            regime=strategy_input.regime,
            regime_probability=strategy_input.regime_probability,
            estimated_cost=strategy_input.cost_estimate,
            slippage_assumption_bps=strategy_input.slippage_bps,
            research_version=strategy_input.versions.get("research"),
            analysis_version=strategy_input.versions.get("analysis"),
            market_version=strategy_input.versions.get("market"),
            prediction_model_version=getattr(strategy_input.prediction, "model_version", None),
            feature_version=strategy_input.versions.get("feature"),
            cost_model_version=self.config.cost_model_version,
            provenance={
                "strategy_id": self.config.strategy_id,
                "strategy_version": self.config.strategy_version,
                "candidate_policy_version": self.config.candidate_policy_version,
            },
        )
        return decision, StrategyTrace(tuple(stages + ["FINAL_DECISION"]), ())

    def _validate_input(self, value: StrategyInput) -> None:
        if not isinstance(value, StrategyInput):
            raise TypeError("strategy_input must be a StrategyInput")

        required = {
            "vwap_distance_pct",
            "rvol_20",
            "higher_high",
            "higher_low",
            "lower_low",
            "lower_high",
        }
        missing = required.difference(value.decision_features)
        if missing:
            raise ValueError(
                "strategy input is missing required fields: "
                f"{sorted(missing)}"
            )

        if value.regime is None or value.regime_probability is None:
            raise ValueError(
                "strategy input requires regime and regime_probability"
            )

        for name, context, exact in (
            ("analysis", value.analysis_context, True),
            ("market", value.market_context, False),
            ("research", value.research_context, False),
        ):
            if context is None:
                continue
            context_timestamp = getattr(context, "timestamp", None)
            if context_timestamp is None:
                continue
            context_timestamp = pd.Timestamp(context_timestamp)
            if context_timestamp.tzinfo is None:
                raise ValueError(
                    f"{name} context timestamp must be timezone-aware"
                )
            if context_timestamp > value.timestamp:
                raise ValueError(
                    f"{name} context cannot be from the future"
                )
            if exact and context_timestamp != value.timestamp:
                raise ValueError(
                    "analysis context timestamp must match strategy timestamp"
                )

        if value.prediction is not None:
            prediction_timestamp = pd.Timestamp(
                getattr(value.prediction, "timestamp", value.timestamp)
            )
            if prediction_timestamp.tzinfo is None:
                raise ValueError(
                    "prediction timestamp must be timezone-aware"
                )
            if prediction_timestamp > value.timestamp:
                raise ValueError(
                    "prediction cannot be from the future"
                )
            if str(getattr(value.prediction, "symbol", "")).strip().upper() != value.symbol:
                raise ValueError(
                    "prediction symbol must match strategy symbol"
                )

    def _regime_reason(self, value: StrategyInput) -> NoTradeReason | None:
        if value.regime_probability < self.config.baseline.minimum_regime_probability:
            return NoTradeReason.REGIME_CONFIDENCE_TOO_LOW
        if value.regime not in self.config.allowed_regimes:
            return NoTradeReason.REGIME_NOT_ELIGIBLE
        return None

    def _analysis_reason(
        self,
        value: StrategyInput,
        direction: StrategyDirection,
    ) -> NoTradeReason | None:
        if not self.config.require_analysis_alignment:
            return None
        context = value.analysis_context
        if context is None:
            return NoTradeReason.MISSING_CONTEXT
        expected = "BULLISH" if direction is StrategyDirection.LONG else "BEARISH"
        if getattr(context, "analytical_direction", None) != expected:
            return NoTradeReason.SIGNAL_CONFLICT
        return None

    def _liquidity_reason(self, value: StrategyInput) -> NoTradeReason | None:
        if value.liquidity_available is None:
            if self.config.require_liquidity_when_present and value.market_context is not None:
                return NoTradeReason.MISSING_CONTEXT
            return None
        return None if value.liquidity_available else NoTradeReason.LIQUIDITY_INSUFFICIENT

    def _cost_reason(self, value: StrategyInput) -> NoTradeReason | None:
        if value.cost_fraction is None:
            return None
        if value.cost_fraction > self.config.max_cost_fraction:
            return NoTradeReason.COST_TOO_HIGH
        if value.cost_estimate is not None and value.cost_estimate < 0:
            return NoTradeReason.INVALID_INPUT
        return None

    def _reject(
        self,
        value: StrategyInput,
        reason: NoTradeReason,
        stages: list[str],
        pred_cls: str | None,
        pred_prob: float | None,
        pred_margin: float | None,
        rationale: str | None = None,
    ) -> tuple[StrategyDecision, StrategyTrace]:
        decision = StrategyDecision(
            timestamp=value.timestamp,
            symbol=value.symbol,
            direction=StrategyDirection.NO_TRADE,
            strategy_version=self.config.strategy_version,
            rationale=rationale or reason.value,
            primary_reason=reason,
            prediction_class=pred_cls,
            prediction_probability=pred_prob,
            prediction_margin=pred_margin,
            regime=value.regime,
            regime_probability=value.regime_probability,
            estimated_cost=value.cost_estimate,
            slippage_assumption_bps=value.slippage_bps,
            research_version=value.versions.get("research"),
            analysis_version=value.versions.get("analysis"),
            market_version=value.versions.get("market"),
            prediction_model_version=getattr(value.prediction, "model_version", None),
            feature_version=value.versions.get("feature"),
            cost_model_version=self.config.cost_model_version,
            provenance={
                "strategy_id": self.config.strategy_id,
                "strategy_version": self.config.strategy_version,
                "reason": reason.value,
            },
        )
        return decision, StrategyTrace(tuple(stages), (reason,))
