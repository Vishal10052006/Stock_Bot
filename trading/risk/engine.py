"""Deterministic broker-free Risk Engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import floor

import pandas as pd

from trading.signals.models import CandidateDirection, TradeCandidate
from trading.signals.validation import validate_candidate

from .calculations import maximum_quantity, reward_risk_ratio
from .contracts import (
    MarketRiskContext,
    PortfolioRiskState,
    RiskDecision,
    RiskDecisionStatus,
    RiskPolicy,
    RiskReasonCode,
)
from .kill_switch import KillSwitch
from .limits import (
    check_daily_loss,
    check_drawdown,
    check_liquidity,
    check_open_positions,
    check_session,
    check_spread,
    check_trade_count,
)


@dataclass(frozen=True, slots=True)
class RiskEvaluationInput:
    """Complete point-in-time input for one risk decision."""
    candidate: TradeCandidate
    portfolio: PortfolioRiskState
    market: MarketRiskContext
    target_price: float | None = None
    sector: str | None = None
    quantity_step: float = 1.0
    quantity_cap: float | None = None
    context_timestamp: pd.Timestamp | None = None

    def __post_init__(self) -> None:
        if self.quantity_step <= 0:
            raise ValueError("quantity_step must be positive")
        if self.quantity_cap is not None and self.quantity_cap <= 0:
            raise ValueError("quantity_cap must be positive")


class RiskEngine:
    """Evaluate candidates under a frozen deterministic risk policy."""

    def __init__(self, *, policy: RiskPolicy | None = None, kill_switch: KillSwitch | None = None) -> None:
        self.policy = policy or RiskPolicy()
        self.kill_switch = kill_switch or KillSwitch()

    def evaluate(self, request: RiskEvaluationInput) -> RiskDecision:
        """Return APPROVED/REDUCED/REJECTED and fail closed on invalid inputs."""
        candidate = request.candidate
        try:
            validate_candidate(candidate)
        except (TypeError, ValueError):
            return self._decision(
                request,
                RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, candidate.stop_distance, None,
                [RiskReasonCode.INVALID_TRADE_CANDIDATE],
                [],
            )

        if self.kill_switch.state.active:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, candidate.stop_distance, None,
                [RiskReasonCode.KILL_SWITCH_ACTIVE], [],
            )

        reasons = self._prechecks(request)
        if reasons:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, candidate.stop_distance, None,
                reasons, [],
            )

        rr = reward_risk_ratio(
            direction=candidate.direction,
            entry_price=candidate.entry_price,
            stop_price=candidate.stop_price,
            target_price=request.target_price,
        )
        if rr is not None and rr < self.policy.min_reward_risk:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, candidate.stop_distance, rr,
                [RiskReasonCode.INVALID_STOP], [],
            )

        multiplier = self.policy.high_volatility_risk_multiplier
        if self.policy.reduce_on_high_volatility and (
            str(request.market.volatility_regime).upper() == "HIGH_VOLATILITY"
        ):
            multiplier = min(multiplier, 1.0)

        position = maximum_quantity(
            equity=request.portfolio.equity,
            candidate=candidate,
            policy=self.policy,
            target_price=request.target_price,
            risk_multiplier=multiplier,
            quantity_step=request.quantity_step,
            quantity_cap=request.quantity_cap,
        )
        if position.quantity <= 0:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, position.risk_per_unit, rr,
                [RiskReasonCode.INSUFFICIENT_CAPITAL], [],
            )

        entry = candidate.entry_price
        cash = max(0.0, request.portfolio.available_cash - request.portfolio.reserved_capital)
        cash_cap = floor(cash / entry / request.quantity_step) * request.quantity_step
        gross_room = max(
            0.0,
            request.portfolio.equity * self.policy.max_gross_exposure
            - request.portfolio.gross_exposure,
        )
        gross_cap = floor(gross_room / entry / request.quantity_step) * request.quantity_step

        symbol_exposure = request.portfolio.symbol_exposure.get(candidate.symbol.upper(), 0.0)
        symbol_room = max(
            0.0,
            request.portfolio.equity * self.policy.max_symbol_exposure - symbol_exposure,
        )
        symbol_cap = floor(symbol_room / entry / request.quantity_step) * request.quantity_step

        sector_key = request.sector or request.market.sector
        sector_exposure = request.portfolio.sector_exposure.get(sector_key, 0.0) if sector_key else 0.0
        sector_room = max(
            0.0,
            request.portfolio.equity * self.policy.max_sector_exposure - sector_exposure,
        )
        sector_cap = floor(sector_room / entry / request.quantity_step) * request.quantity_step

        quantity = min(position.quantity, cash_cap, gross_cap, symbol_cap, sector_cap)
        quantity = floor(quantity / request.quantity_step) * request.quantity_step
        if quantity <= 0:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, position.risk_per_unit, rr,
                [RiskReasonCode.POSITION_SIZE_TOO_LARGE], [],
            )

        notional = quantity * entry
        liquidity = check_liquidity(request.market, quantity, self.policy)
        if not liquidity.passed:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, position.risk_per_unit, rr,
                [liquidity.reason or RiskReasonCode.LIQUIDITY_TOO_LOW], [],
            )

        gross_after = request.portfolio.gross_exposure + notional
        signed = notional if candidate.direction is CandidateDirection.LONG else -notional
        net_after = request.portfolio.net_exposure + signed

        if gross_after > request.portfolio.equity * self.policy.max_gross_exposure + 1e-9:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, position.risk_per_unit, rr,
                [RiskReasonCode.GROSS_EXPOSURE_LIMIT], [],
            )
        if abs(net_after) > request.portfolio.equity * self.policy.max_net_exposure + 1e-9:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, position.risk_per_unit, rr,
                [RiskReasonCode.NET_EXPOSURE_LIMIT], [],
            )
        if request.portfolio.equity > 0 and gross_after / request.portfolio.equity > self.policy.max_leverage + 1e-9:
            return self._decision(
                request, RiskDecisionStatus.REJECTED,
                0.0, 0.0, 0.0, position.risk_per_unit, rr,
                [RiskReasonCode.LEVERAGE_LIMIT], [],
            )

        planned_risk = quantity * candidate.stop_distance
        risk_budget = request.portfolio.equity * self.policy.risk_per_trade
        status = RiskDecisionStatus.APPROVED
        restrictions: list[str] = []
        reasons = [RiskReasonCode.MAX_RISK_EXCEEDED]
        if quantity < position.quantity:
            status = RiskDecisionStatus.REDUCED
            restrictions.append("quantity_capped_by_capital_exposure_or_sector_limits")
            reasons = [RiskReasonCode.POSITION_SIZE_TOO_LARGE]

        utilization = planned_risk / max(risk_budget, 1e-12)
        if status is RiskDecisionStatus.APPROVED:
            reasons = [RiskReasonCode.MAX_RISK_EXCEEDED]

        return self._decision(
            request, status, quantity, notional, planned_risk, position.risk_per_unit,
            rr, reasons, restrictions, gross_after, net_after, utilization,
        )

    def _prechecks(self, request: RiskEvaluationInput) -> list[RiskReasonCode]:
        """Run causal context and account hard-limit checks."""
        reasons: list[RiskReasonCode] = []
        candidate_ts = pd.Timestamp(request.candidate.timestamp)
        context_ts = pd.Timestamp(request.context_timestamp or candidate_ts)
        for ts in (
            candidate_ts,
            pd.Timestamp(request.market.timestamp),
            pd.Timestamp(request.portfolio.timestamp),
        ):
            if abs((context_ts - ts).total_seconds()) > self.policy.stale_context_seconds:
                reasons.append(RiskReasonCode.STALE_CONTEXT)
                break

        for result in (
            check_session(request.market, self.policy),
            check_trade_count(request.portfolio, self.policy),
            check_open_positions(request.portfolio, self.policy),
            check_daily_loss(request.portfolio, self.policy),
            check_drawdown(request.portfolio, self.policy),
            check_spread(request.market, self.policy),
        ):
            if not result.passed and result.reason is not None:
                reasons.append(result.reason)

        if request.market.stress_flag:
            reasons.append(RiskReasonCode.MARKET_STRESS)

        return list(dict.fromkeys(reasons))

    def _decision(
        self,
        request: RiskEvaluationInput,
        status: RiskDecisionStatus,
        quantity: float,
        notional: float,
        planned_risk: float,
        risk_per_unit: float,
        rr: float | None,
        reasons: list[RiskReasonCode],
        restrictions: list[str],
        gross_after: float | None = None,
        net_after: float | None = None,
        utilization: float = 0.0,
    ) -> RiskDecision:
        """Create stable, auditable immutable lineage."""
        timestamp = pd.Timestamp(request.candidate.timestamp)
        payload = {
            "timestamp": str(timestamp),
            "symbol": request.candidate.symbol.upper(),
            "direction": request.candidate.direction.value,
            "quantity": float(quantity),
            "notional": float(notional),
            "status": status.value,
            "policy": self.policy.policy_version,
            "candidate_policy": request.candidate.policy_version,
        }
        decision_id = "risk-" + sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:20]
        return RiskDecision(
            decision_id=decision_id,
            timestamp=timestamp,
            symbol=request.candidate.symbol.upper(),
            direction=request.candidate.direction,
            status=status,
            approved_quantity=float(quantity),
            approved_notional=float(notional),
            planned_risk=float(planned_risk),
            risk_per_unit=float(risk_per_unit),
            reward_risk_ratio=rr,
            gross_exposure_before=float(request.portfolio.gross_exposure),
            gross_exposure_after=float(
                request.portfolio.gross_exposure if gross_after is None else gross_after
            ),
            net_exposure_before=float(request.portfolio.net_exposure),
            net_exposure_after=float(
                request.portfolio.net_exposure if net_after is None else net_after
            ),
            risk_utilization=float(utilization),
            reason_codes=tuple(dict.fromkeys(reasons)),
            restrictions=tuple(restrictions),
            risk_policy_version=self.policy.policy_version,
            candidate_policy_version=request.candidate.policy_version,
            created_at=datetime.now(timezone.utc),
            provenance={"engine": "trading.risk.engine", "policy": self.policy.policy_version},
        )
