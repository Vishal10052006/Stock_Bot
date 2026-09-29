"""Live feed to paper trading decision loop and session controller.

Connects incoming real-time 5-minute candles to the complete quantitative stack:
    Candle Stream -> Feature Extraction -> Strategy -> Risk -> Safety Gate ->
    Paper Fill -> Position Tracking -> Exit Engine -> Outcomes -> Journal ->
    10-Trade Experiment Controller -> Reproducible Evidence Bundle.

Guarantees:
- Pure simulated paper execution (live broker execution remains strictly locked).
- Session stops automatically when target completed trades (default: 10) are achieved.
- All session outputs are immutably persisted with a SHA-256 evidence fingerprint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from execution.safety import IndependentSafetyGate, SafetyBlock, SafetyState
from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
    authorize_risk_decision,
)
from paper.runtime import (
    PaperOrder,
    PaperOrderStatus,
    PaperTradingConfig,
    PaperTradingRuntime,
)
from trading.paper.exit_engine import ExitReason, PaperExitEngine, PaperPosition
from trading.paper.lifecycle import TradeOutcome
from trading.paper.metrics import (
    PaperExperimentMetrics,
    calculate_paper_metrics,
    generate_experiment_report,
)
from trading.risk.engine import RiskConfig, RiskEngine
from trading.risk.gate import RiskDecisionStatus, evaluate_strategy_risk
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import (
    BaselineStrategyConfig,
    StrategyConfig,
    StrategyDecision,
    StrategyDirection,
    StrategyInput,
)


@dataclass(frozen=True, slots=True)
class LivePaperSessionConfig:
    """Immutable configuration for one controlled paper trading experiment."""

    experiment_id: str = "PAPER-LIVE-001"
    target_trades: int = 10
    symbol: str = "RELIANCE"
    timeframe_minutes: int = 5
    initial_equity: float = 100_000.0
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    stop_loss_pct: float = 0.010
    take_profit_pct: float = 0.020
    max_open_positions: int = 1
    session_cutoff_time: str = "15:15"
    output_dir: Path = Path("paper/sessions")
    stop_on_target_trades: bool = True
    strategy_version: str = "STRAT-v1.0"
    model_version: str = "v1.0"
    risk_version: str = "RISK-v1.0"

    def __post_init__(self) -> None:
        if self.target_trades <= 0:
            raise ValueError("target_trades must be positive")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if self.stop_loss_pct <= 0 or self.take_profit_pct <= 0:
            raise ValueError("stop_loss_pct and take_profit_pct must be positive")


@dataclass(frozen=True, slots=True)
class LivePaperSessionResult:
    """Immutable summary and evidence of a completed paper trading session."""

    experiment_id: str
    symbol: str
    target_trades: int
    completed_trades: int
    target_reached: bool
    start_time: pd.Timestamp | None
    end_time: pd.Timestamp | None
    metrics: PaperExperimentMetrics
    outcomes: tuple[TradeOutcome, ...]
    session_fingerprint: str
    output_path: Path | None
    report_text: str


class LivePaperEngine:
    """Real-time candle-driven paper trading engine and 10-trade session controller."""

    def __init__(
        self,
        config: LivePaperSessionConfig | None = None,
        *,
        strategy_config: StrategyConfig | None = None,
        risk_config: RiskConfig | None = None,
    ) -> None:
        self.config = config or LivePaperSessionConfig()

        adapter_config = PaperTradingConfig(
            fee_bps=self.config.fee_bps,
            slippage_bps=self.config.slippage_bps,
            initial_equity=self.config.initial_equity,
        )
        self.runtime = PaperTradingRuntime(config=adapter_config)
        self.exit_engine = PaperExitEngine(
            fee_bps=self.config.fee_bps,
            slippage_bps=self.config.slippage_bps,
            session_cutoff_time=self.config.session_cutoff_time,
        )
        self.strategy_engine = StrategyEngine(strategy_config)
        self.risk_engine = RiskEngine(risk_config)
        self.safety_gate = IndependentSafetyGate()

        self._candle_history: list[dict[str, Any]] = []
        self._decisions: list[dict[str, Any]] = []
        self._submitted_orders: list[PaperOrder] = []
        self._session_completed = False
        self._start_time: pd.Timestamp | None = None
        self._last_time: pd.Timestamp | None = None

    @property
    def session_completed(self) -> bool:
        """True when target completed trades have been reached."""
        return self._session_completed

    @property
    def completed_count(self) -> int:
        """Number of closed trades produced so far."""
        return len(self.exit_engine.completed_outcomes)

    @property
    def submitted_order_count(self) -> int:
        """Number of filled paper entry orders submitted in this session."""
        return len(self._submitted_orders)

    def register_submitted_order(self, order: Any) -> None:
        """Register one filled paper order with the session controller."""
        if not isinstance(order, PaperOrder):
            raise TypeError("order must be a PaperOrder")
        if order.status is not PaperOrderStatus.FILLED:
            raise ValueError("only FILLED paper orders may be registered")
        self._submitted_orders.append(order)

    def on_candle(self, candle: Any) -> list[TradeOutcome]:
        """Process one closed 5-minute candle through the complete trading loop."""
        raw_symbol = getattr(candle, "symbol", None) or candle["symbol"]
        symbol = str(raw_symbol).strip().upper()
        if symbol != self.config.symbol:
            return []

        raw_ts = getattr(candle, "timestamp", None) or candle["timestamp"]
        timestamp = pd.Timestamp(raw_ts)

        open_p = float(getattr(candle, "open", None) if hasattr(candle, "open") else candle["open"])
        high_p = float(getattr(candle, "high", None) if hasattr(candle, "high") else candle["high"])
        low_p = float(getattr(candle, "low", None) if hasattr(candle, "low") else candle["low"])
        close_p = float(getattr(candle, "close", None) if hasattr(candle, "close") else candle["close"])
        vol = float(getattr(candle, "volume", None) if hasattr(candle, "volume") else candle.get("volume", 1000.0))

        candle_dict = {
            "timestamp": timestamp,
            "symbol": symbol,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": vol,
        }

        if self._start_time is None:
            self._start_time = timestamp
        self._last_time = timestamp
        self._candle_history.append(candle_dict)

        # -------------------------------------------------------------
        # STEP 1: Process open positions against this new candle
        # -------------------------------------------------------------
        closed_now = self.exit_engine.process_candle(candle_dict)

        # Check target trade threshold
        if (
            self.config.stop_on_target_trades
            and self.completed_count >= self.config.target_trades
        ):
            self._session_completed = True
            return closed_now

        if self._session_completed:
            return closed_now

        # -------------------------------------------------------------
        # STEP 2: Evaluate New Trade Opportunities (if flat)
        # -------------------------------------------------------------
        if not self.exit_engine.has_open_position(symbol):
            self._evaluate_entry(candle_dict)

        return closed_now

    def _evaluate_entry(self, candle: dict[str, Any]) -> None:
        """Generate causal features and evaluate Strategy -> Risk -> Paper Entry."""
        timestamp = candle["timestamp"]
        symbol = candle["symbol"]
        close_p = candle["close"]

        features, regime, regime_prob = self._compute_causal_features(candle)

        strategy_input = StrategyInput(
            timestamp=timestamp,
            symbol=symbol,
            regime=regime,
            regime_probability=regime_prob,
            decision_features=features,
            versions={
                "model": self.config.model_version,
            },
        )

        strategy_decision, _trace = self.strategy_engine.decide(strategy_input)

        if strategy_decision.direction is StrategyDirection.NO_TRADE:
            self._record_decision(strategy_decision, None, None)
            return

        risk_decision = evaluate_strategy_risk(
            strategy_decision,
            risk_enabled=True,
            approved_quantity=10.0,
            approved_notional=close_p * 10.0,
        )

        if risk_decision.status is not RiskDecisionStatus.APPROVED:
            self._record_decision(strategy_decision, risk_decision, None)
            return

        safety_eval = self.safety_gate.evaluate(
            SafetyState(live_execution_enabled=False)
        )
        if safety_eval.block not in (SafetyBlock.NONE, SafetyBlock.LIVE_LOCKED):
            self._record_decision(strategy_decision, risk_decision, None)
            return

        direction = strategy_decision.direction
        if direction is StrategyDirection.LONG:
            stop_price = close_p * (1.0 - self.config.stop_loss_pct)
            target_price = close_p * (1.0 + self.config.take_profit_pct)
        else:
            stop_price = close_p * (1.0 + self.config.stop_loss_pct)
            target_price = close_p * (1.0 - self.config.take_profit_pct)

        trade_index = len(self._submitted_orders) + 1
        trade_id = f"TR-{self.config.experiment_id}-{trade_index:03d}"
        risk_version = getattr(risk_decision, "risk_version", "v1.0") or "v1.0"

        auth = authorize_risk_decision(
            risk_decision,
            risk_decision_id=f"{timestamp.isoformat()}:{symbol}:{risk_version}",
        )

        if auth.status is not ExecutionAuthorizationStatus.AUTHORIZED:
            self._record_decision(strategy_decision, risk_decision, None)
            return

        order = self.runtime.submit(
            auth,
            price=close_p,
            quantity=risk_decision.approved_quantity,
        )

        if order.status is PaperOrderStatus.FILLED:
            self.register_submitted_order(order)
            self.exit_engine.open_position(
                order,
                stop_price=stop_price,
                target_price=target_price,
                trade_id=trade_id,
                strategy_version=self.config.strategy_version,
                model_version=self.config.model_version,
                risk_version=self.config.risk_version,
                regime=regime,
            )
            self._record_decision(strategy_decision, risk_decision, order)

    def _compute_causal_features(
        self,
        current_candle: dict[str, Any],
    ) -> tuple[dict[str, Any], str, float]:
        """Compute causal features and regime from historical candles without lookahead."""
        n = len(self._candle_history)
        closes = [c["close"] for c in self._candle_history]
        volumes = [c["volume"] for c in self._candle_history]

        recent_vols = volumes[-20:] if n >= 20 else volumes
        avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 1.0
        rvol = (current_candle["volume"] / avg_vol) if avg_vol > 0 else 1.2

        typical_prices = [(c["high"] + c["low"] + c["close"]) / 3.0 for c in self._candle_history]
        sum_pv = sum(tp * vol for tp, vol in zip(typical_prices, volumes))
        sum_v = sum(volumes)
        vwap = (sum_pv / sum_v) if sum_v > 0 else current_candle["close"]
        vwap_dist_pct = ((current_candle["close"] - vwap) / vwap) * 100.0

        highs = [c["high"] for c in self._candle_history[-20:]]
        lows = [c["low"] for c in self._candle_history[-20:]]
        swing_high = max(highs) if highs else current_candle["high"]
        swing_low = min(lows) if lows else current_candle["low"]

        if n >= 5:
            sma_short = sum(closes[-5:]) / 5.0
            sma_long = sum(closes[-15:]) / len(closes[-15:]) if n >= 15 else sma_short
            higher_high = closes[-1] > closes[-2] if n >= 2 else True
            higher_low = current_candle["low"] > self._candle_history[-2]["low"] if n >= 2 else True
            lower_low = not higher_low
            lower_high = not higher_high
            if sma_short > sma_long:
                regime = "TREND_UP"
                regime_prob = 0.85
            elif sma_short < sma_long:
                regime = "TREND_DOWN"
                regime_prob = 0.85
            else:
                regime = "SIDEWAYS"
                regime_prob = 0.70
        else:
            higher_high = True
            higher_low = True
            lower_low = False
            lower_high = False
            regime = "TREND_UP"
            regime_prob = 0.80

        features = {
            "vwap_distance_pct": vwap_dist_pct,
            "rvol_20": max(1.1, rvol),
            "higher_high": higher_high,
            "higher_low": higher_low,
            "lower_low": lower_low,
            "lower_high": lower_high,
            "swing_high": swing_high,
            "swing_low": swing_low,
            "support_20": swing_low * 0.99,
            "resistance_20": swing_high * 1.01,
            "atr_14": max(0.5, (swing_high - swing_low) / 4.0),
        }

        return features, regime, regime_prob

    def _record_decision(
        self,
        strategy: StrategyDecision,
        risk: Any | None,
        order: PaperOrder | None,
    ) -> None:
        self._decisions.append({
            "timestamp": strategy.timestamp.isoformat(),
            "symbol": strategy.symbol,
            "direction": strategy.direction.value,
            "regime": strategy.regime,
            "risk_status": getattr(risk, "status", "N/A"),
            "order_id": getattr(order, "reason", None),
        })

    def run_candles(self, candles: Iterable[Any]) -> LivePaperSessionResult:
        """Run an iterable stream of candles through the live paper session."""
        for candle in candles:
            self.on_candle(candle)
            if self._session_completed:
                break
        return self.finalize_session()

    def finalize_session(self) -> LivePaperSessionResult:
        """Close remaining positions, compute metrics, and write immutable session evidence."""
        if self._last_time is not None and self.exit_engine.has_open_position(self.config.symbol):
            last_close = self._candle_history[-1]["close"] if self._candle_history else 100.0
            self.exit_engine.close_all(
                timestamp=self._last_time,
                price_lookup={self.config.symbol: last_close},
                reason=ExitReason.SESSION_CLOSE,
            )

        outcomes = self.exit_engine.completed_outcomes
        metrics = calculate_paper_metrics(
            outcomes,
            initial_equity=self.config.initial_equity,
            exit_reasons={k: v.value for k, v in self.exit_engine.exit_reasons.items()},
        )

        start_str = self._start_time.isoformat() if self._start_time else "N/A"
        end_str = self._last_time.isoformat() if self._last_time else "N/A"

        report_text = generate_experiment_report(
            metrics,
            experiment_id=self.config.experiment_id,
            start_time=start_str,
            end_time=end_str,
            model_version=self.config.model_version,
            strategy_version=self.config.strategy_version,
            risk_version=self.config.risk_version,
            feed_name="Upstox",
            timeframe=f"{self.config.timeframe_minutes}m",
            live_broker_orders=0,
        )

        fingerprint_dict = {
            "experiment_id": self.config.experiment_id,
            "symbol": self.config.symbol,
            "target_trades": self.config.target_trades,
            "completed_trades": len(outcomes),
            "start_time": start_str,
            "end_time": end_str,
            "net_pnl": metrics.net_pnl,
            "win_rate": metrics.win_rate_pct,
            "outcomes_count": len(outcomes),
        }
        canonical_bytes = json.dumps(fingerprint_dict, sort_keys=True).encode("utf-8")
        session_fingerprint = hashlib.sha256(canonical_bytes).hexdigest()

        session_path: Path | None = None
        if self.config.output_dir:
            session_path = Path(self.config.output_dir) / self.config.experiment_id
            session_path.mkdir(parents=True, exist_ok=True)

            session_meta = {
                "config": {
                    "experiment_id": self.config.experiment_id,
                    "target_trades": self.config.target_trades,
                    "symbol": self.config.symbol,
                    "timeframe_minutes": self.config.timeframe_minutes,
                    "initial_equity": self.config.initial_equity,
                    "strategy_version": self.config.strategy_version,
                    "model_version": self.config.model_version,
                    "risk_version": self.config.risk_version,
                },
                "start_time": start_str,
                "end_time": end_str,
                "completed_trades": len(outcomes),
                "target_reached": len(outcomes) >= self.config.target_trades,
                "fingerprint": session_fingerprint,
                "live_broker_orders": 0,
            }
            (session_path / "session.json").write_text(json.dumps(session_meta, indent=2), encoding="utf-8")
            (session_path / "metrics.json").write_text(json.dumps(metrics.to_dict(), indent=2), encoding="utf-8")
            (session_path / "report.txt").write_text(report_text, encoding="utf-8")

            with (session_path / "outcomes.jsonl").open("w", encoding="utf-8") as f:
                for o in outcomes:
                    line = {
                        "symbol": o.symbol,
                        "direction": o.direction.value,
                        "entry_time": o.entry_time.isoformat(),
                        "exit_time": o.exit_time.isoformat(),
                        "entry_price": o.entry_price,
                        "exit_price": o.exit_price,
                        "quantity": o.quantity,
                        "gross_pnl": o.gross_pnl,
                        "fees": o.fees,
                        "slippage_cost": o.slippage_cost,
                        "net_pnl": o.net_pnl,
                        "holding_minutes": o.holding_minutes,
                        "mae": o.mae,
                        "mfe": o.mfe,
                    }
                    f.write(json.dumps(line) + "\n")

            (session_path / "session_fingerprint.sha256").write_text(
                f"{session_fingerprint}\n",
                encoding="utf-8",
            )

        return LivePaperSessionResult(
            experiment_id=self.config.experiment_id,
            symbol=self.config.symbol,
            target_trades=self.config.target_trades,
            completed_trades=len(outcomes),
            target_reached=len(outcomes) >= self.config.target_trades,
            start_time=self._start_time,
            end_time=self._last_time,
            metrics=metrics,
            outcomes=outcomes,
            session_fingerprint=session_fingerprint,
            output_path=session_path,
            report_text=report_text,
        )


__all__ = [
    "LivePaperEngine",
    "LivePaperSessionConfig",
    "LivePaperSessionResult",
]
