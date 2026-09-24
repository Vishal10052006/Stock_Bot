"""Monitoring metric state and immutable snapshots.

References:
    docs/MONITORING_ENGINE.md
    market/data/metrics/data_quality.py
    ml/prediction/monitoring.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from statistics import mean


def _p95(values: tuple[float, ...]) -> float | None:
    """Return deterministic nearest-rank P95."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


@dataclass(frozen=True, slots=True)
class SystemMetrics:
    """System health counters."""

    heartbeat_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    latency_samples_ms: tuple[float, ...] = ()
    restarts: int = 0

    @property
    def error_rate(self) -> float:
        """Return errors per heartbeat."""
        return self.error_count / max(self.heartbeat_count, 1)

    @property
    def latency_p95_ms(self) -> float | None:
        """Return telemetry latency P95."""
        return _p95(self.latency_samples_ms)


@dataclass(frozen=True, slots=True)
class ModelMetrics:
    """Prediction and calibration observations."""

    predictions: int = 0
    outcomes_observed: int = 0
    correct_predictions: int = 0
    log_loss_sum: float = 0.0
    brier_sum: float = 0.0
    long_probabilities: tuple[float, ...] = ()
    short_probabilities: tuple[float, ...] = ()
    no_edge_probabilities: tuple[float, ...] = ()

    @property
    def accuracy(self) -> float | None:
        """Return observed accuracy."""
        if self.outcomes_observed == 0:
            return None
        return self.correct_predictions / self.outcomes_observed

    @property
    def mean_log_loss(self) -> float | None:
        """Return observed mean log loss."""
        if self.outcomes_observed == 0:
            return None
        return self.log_loss_sum / self.outcomes_observed

    @property
    def mean_brier(self) -> float | None:
        """Return observed mean multiclass Brier score."""
        if self.outcomes_observed == 0:
            return None
        return self.brier_sum / self.outcomes_observed


@dataclass(frozen=True, slots=True)
class StrategyMetrics:
    """Strategy behavior observations."""

    candidate_count: int = 0
    trade_count: int = 0
    long_count: int = 0
    short_count: int = 0
    no_trade_count: int = 0
    wins: int = 0
    losses: int = 0
    pnl_sum: float = 0.0
    r_sum: float = 0.0

    @property
    def no_trade_rate(self) -> float:
        """Return NO_TRADE ratio."""
        return self.no_trade_count / max(self.candidate_count, 1)

    @property
    def win_rate(self) -> float | None:
        """Return realized win rate."""
        completed = self.wins + self.losses
        if completed == 0:
            return None
        return self.wins / completed

    @property
    def average_r(self) -> float | None:
        """Return mean realized R multiple."""
        if self.trade_count == 0:
            return None
        return self.r_sum / self.trade_count


@dataclass(frozen=True, slots=True)
class RiskMetrics:
    """Portfolio and risk-control observations."""

    equity: float = 0.0
    starting_equity: float = 0.0
    daily_pnl: float = 0.0
    open_positions: int = 0
    gross_exposure: float = 0.0
    rejected_by_risk: int = 0
    kill_switch_active: bool = False

    @property
    def drawdown(self) -> float:
        """Return absolute decline from starting equity."""
        return max(self.starting_equity - self.equity, 0.0)

    @property
    def daily_loss_fraction(self) -> float:
        """Return daily loss as a fraction of starting equity."""
        if self.starting_equity <= 0:
            return 0.0
        return max(-self.daily_pnl / self.starting_equity, 0.0)


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    """Order and fill quality observations."""

    orders_created: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    partial_fills: int = 0
    duplicate_orders: int = 0
    reconciliations: int = 0
    reconciliation_mismatches: int = 0
    slippage_bps: tuple[float, ...] = ()
    order_latency_ms: tuple[float, ...] = ()

    @property
    def fill_rate(self) -> float:
        """Return filled-orders ratio."""
        return self.orders_filled / max(self.orders_created, 1)

    @property
    def rejection_rate(self) -> float:
        """Return rejected-orders ratio."""
        return self.orders_rejected / max(self.orders_created, 1)

    @property
    def mean_slippage_bps(self) -> float | None:
        """Return mean observed slippage."""
        if not self.slippage_bps:
            return None
        return mean(self.slippage_bps)

    @property
    def p95_order_latency_ms(self) -> float | None:
        """Return order latency P95."""
        return _p95(self.order_latency_ms)


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Immutable monitoring state consumed by evaluators."""

    system: SystemMetrics
    model: ModelMetrics
    strategy: StrategyMetrics
    risk: RiskMetrics
    execution: ExecutionMetrics


@dataclass(slots=True)
class MetricsAccumulator:
    """Mutable collector producing immutable metrics."""

    heartbeat_count: int = 0
    system_errors: int = 0
    system_warnings: int = 0
    system_latency_ms: list[float] = field(default_factory=list)
    restarts: int = 0

    predictions: int = 0
    outcomes_observed: int = 0
    correct_predictions: int = 0
    log_loss_sum: float = 0.0
    brier_sum: float = 0.0
    long_probabilities: list[float] = field(default_factory=list)
    short_probabilities: list[float] = field(default_factory=list)
    no_edge_probabilities: list[float] = field(default_factory=list)

    candidate_count: int = 0
    trade_count: int = 0
    long_count: int = 0
    short_count: int = 0
    no_trade_count: int = 0
    wins: int = 0
    losses: int = 0
    pnl_sum: float = 0.0
    r_sum: float = 0.0

    equity: float = 0.0
    starting_equity: float = 0.0
    daily_pnl: float = 0.0
    open_positions: int = 0
    gross_exposure: float = 0.0
    rejected_by_risk: int = 0
    kill_switch_active: bool = False

    orders_created: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    partial_fills: int = 0
    duplicate_orders: int = 0
    reconciliations: int = 0
    reconciliation_mismatches: int = 0
    slippage_bps: list[float] = field(default_factory=list)
    order_latency_ms: list[float] = field(default_factory=list)

    def snapshot(self) -> MetricsSnapshot:
        """Freeze collector state."""
        return MetricsSnapshot(
            system=SystemMetrics(
                heartbeat_count=self.heartbeat_count,
                error_count=self.system_errors,
                warning_count=self.system_warnings,
                latency_samples_ms=tuple(self.system_latency_ms),
                restarts=self.restarts,
            ),
            model=ModelMetrics(
                predictions=self.predictions,
                outcomes_observed=self.outcomes_observed,
                correct_predictions=self.correct_predictions,
                log_loss_sum=self.log_loss_sum,
                brier_sum=self.brier_sum,
                long_probabilities=tuple(self.long_probabilities),
                short_probabilities=tuple(self.short_probabilities),
                no_edge_probabilities=tuple(self.no_edge_probabilities),
            ),
            strategy=StrategyMetrics(
                candidate_count=self.candidate_count,
                trade_count=self.trade_count,
                long_count=self.long_count,
                short_count=self.short_count,
                no_trade_count=self.no_trade_count,
                wins=self.wins,
                losses=self.losses,
                pnl_sum=self.pnl_sum,
                r_sum=self.r_sum,
            ),
            risk=RiskMetrics(
                equity=self.equity,
                starting_equity=self.starting_equity,
                daily_pnl=self.daily_pnl,
                open_positions=self.open_positions,
                gross_exposure=self.gross_exposure,
                rejected_by_risk=self.rejected_by_risk,
                kill_switch_active=self.kill_switch_active,
            ),
            execution=ExecutionMetrics(
                orders_created=self.orders_created,
                orders_filled=self.orders_filled,
                orders_rejected=self.orders_rejected,
                partial_fills=self.partial_fills,
                duplicate_orders=self.duplicate_orders,
                reconciliations=self.reconciliations,
                reconciliation_mismatches=self.reconciliation_mismatches,
                slippage_bps=tuple(self.slippage_bps),
                order_latency_ms=tuple(self.order_latency_ms),
            ),
        )
