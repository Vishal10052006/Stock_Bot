"""Virtual intraday paper-account session controller.

This module composes the existing canonical live-paper orchestrator with an
explicit virtual account/session boundary. It never places broker orders.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import pandas as pd

from market.candles.models import Candle
from trading.paper.canonical_live_orchestrator import CanonicalLivePaperOrchestrator
from trading.paper.live_loop import LivePaperSessionResult


@dataclass(frozen=True, slots=True)
class VirtualAccountSnapshot:
    """Point-in-time virtual account state at a completed candle."""

    timestamp: pd.Timestamp
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    gross_exposure: float
    open_positions: int

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("snapshot timestamp must be timezone-aware")

        for name in (
            "equity",
            "realized_pnl",
            "unrealized_pnl",
            "gross_exposure",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")

        if self.gross_exposure < 0 or self.open_positions < 0:
            raise ValueError("account exposure and positions must be non-negative")

        object.__setattr__(self, "timestamp", timestamp)


@dataclass(frozen=True, slots=True)
class VirtualIntradaySessionConfig:
    """Configuration for one full-session virtual intraday run."""

    initial_equity: float = 100_000.0
    output_dir: Path = Path("paper/virtual_sessions")
    session_id: str = "VIRTUAL-INTRADAY-001"

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.initial_equity)) or self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive and finite")
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")


class VirtualIntradaySession:
    """Run the canonical trading pipeline against a virtual account.

    All trading decisions and paper fills remain owned by the existing
    canonical orchestrator and LivePaperEngine. This class only adds
    full-session account snapshots and an auditable account ledger.
    """

    def __init__(
        self,
        orchestrator: CanonicalLivePaperOrchestrator,
        *,
        config: VirtualIntradaySessionConfig | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.config = config or VirtualIntradaySessionConfig()

        actual_initial = float(orchestrator.paper_engine.config.initial_equity)
        if actual_initial != float(self.config.initial_equity):
            raise ValueError(
                "virtual session initial_equity must match paper engine initial_equity"
            )

        if orchestrator.paper_engine.config.stop_on_target_trades:
            raise ValueError(
                "paper engine must use stop_on_target_trades=False for a full intraday session"
            )

        self._snapshots: list[VirtualAccountSnapshot] = []

    @property
    def snapshots(self) -> tuple[VirtualAccountSnapshot, ...]:
        """Return immutable account snapshots."""
        return tuple(self._snapshots)

    def process_candle(self, candle: Candle):
        """Process one completed candle and record the account mark."""
        prediction = self.orchestrator.process_candle(candle)

        symbol = candle.symbol.strip().upper()
        price = float(candle.close)
        engine = self.orchestrator.paper_engine
        equity, realized, unrealized, gross = engine.runtime.account_snapshot(
            {symbol: price}
        )

        self._snapshots.append(
            VirtualAccountSnapshot(
                timestamp=pd.Timestamp(candle.timestamp),
                equity=equity,
                realized_pnl=realized,
                unrealized_pnl=unrealized,
                gross_exposure=gross,
                open_positions=len(engine.runtime.positions),
            )
        )
        return prediction

    def run_candles(self, candles: Iterable[Candle]) -> LivePaperSessionResult:
        """Process a chronological completed-candle stream for the session."""
        previous: pd.Timestamp | None = None

        for candle in candles:
            timestamp = pd.Timestamp(candle.timestamp)
            if timestamp.tzinfo is None:
                raise ValueError("session candles must be timezone-aware")
            if previous is not None and timestamp <= previous:
                raise ValueError("session candles must be strictly chronological")
            previous = timestamp
            self.process_candle(candle)

        return self.finalize()

    def finalize(self) -> LivePaperSessionResult:
        """Finalize the paper engine and persist the account ledger."""
        result = self.orchestrator.paper_engine.finalize_session()

        output_path = Path(self.config.output_dir) / self.config.session_id
        output_path.mkdir(parents=True, exist_ok=True)

        ledger_path = output_path / "account_ledger.jsonl"
        with ledger_path.open("w", encoding="utf-8") as handle:
            for snapshot in self._snapshots:
                handle.write(
                    json.dumps(
                        {
                            "timestamp": snapshot.timestamp.isoformat(),
                            "equity": snapshot.equity,
                            "realized_pnl": snapshot.realized_pnl,
                            "unrealized_pnl": snapshot.unrealized_pnl,
                            "gross_exposure": snapshot.gross_exposure,
                            "open_positions": snapshot.open_positions,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )

        final = self._snapshots[-1] if self._snapshots else None
        summary = {
            "session_id": self.config.session_id,
            "initial_equity": self.config.initial_equity,
            "final_equity": final.equity if final else self.config.initial_equity,
            "realized_pnl": final.realized_pnl if final else 0.0,
            "unrealized_pnl": final.unrealized_pnl if final else 0.0,
            "gross_exposure": final.gross_exposure if final else 0.0,
            "open_positions": final.open_positions if final else 0,
            "completed_trades": result.completed_trades,
            "live_broker_orders": 0,
            "account_ledger": str(ledger_path),
        }

        canonical = json.dumps(summary, sort_keys=True, separators=(",", ":"))
        summary["fingerprint"] = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        (output_path / "account_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return result


__all__ = [
    "VirtualAccountSnapshot",
    "VirtualIntradaySession",
    "VirtualIntradaySessionConfig",
]
