"""Virtual intraday paper-account session controller.

This module composes the existing canonical live-paper orchestrator with an
explicit virtual account/session boundary. It never places broker orders.

The account ledger is derived from the paper trade lifecycle, not from the
execution runtime alone. This is important because the runtime records entry
fills while the exit engine owns lifecycle closure and TradeOutcome P&L.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable
import re

import pandas as pd

from market.candles.models import Candle
from trading.paper.canonical_live_orchestrator import CanonicalLivePaperOrchestrator
from trading.paper.exit_engine import PaperPosition
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
    market_timezone: str = "Asia/Kolkata"
    session_open: str = "09:15"
    session_close: str = "15:30"

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.initial_equity)) or self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive and finite")
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if not self.market_timezone.strip():
            raise ValueError("market_timezone must not be empty")
        for name, value in (
            ("session_open", self.session_open),
            ("session_close", self.session_close),
        ):
            if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) is None:
                raise ValueError(f"{name} must use HH:MM format")


class VirtualIntradaySession:
    """Run the canonical trading pipeline against a virtual account.

    All trading decisions and paper fills remain owned by the existing
    canonical orchestrator and LivePaperEngine. This class adds only the
    full-session account boundary and auditable account ledger.
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
        self._session_date: pd.Timestamp | None = None

    @property
    def snapshots(self) -> tuple[VirtualAccountSnapshot, ...]:
        """Return immutable account snapshots."""
        return tuple(self._snapshots)

    def _account_mark(
        self,
        *,
        timestamp: pd.Timestamp,
        prices: dict[str, float],
    ) -> VirtualAccountSnapshot:
        """Build an account mark from lifecycle outcomes and open positions.

        Completed TradeOutcome records are the authoritative realized P&L.
        Open PaperPosition objects provide causal mark-to-market state. Entry
        fees for open positions are subtracted because those costs are already
        incurred but cannot yet appear in a closed TradeOutcome.
        """
        engine = self.orchestrator.paper_engine

        realized_pnl = sum(
            float(outcome.net_pnl)
            for outcome in engine.exit_engine.completed_outcomes
        )

        unrealized_pnl = 0.0
        gross_exposure = 0.0
        open_positions = engine.exit_engine.all_open_positions()

        for position in open_positions:
            symbol = position.symbol.upper()
            if symbol not in prices:
                raise ValueError(f"missing mark price for open position {symbol}")

            price = float(prices[symbol])
            if not math.isfinite(price) or price <= 0:
                raise ValueError(
                    f"mark price for {symbol} must be positive and finite"
                )

            if position.direction.value == "LONG":
                unrealized_pnl += (
                    price - position.fill_price
                ) * position.quantity
            else:
                unrealized_pnl += (
                    position.fill_price - price
                ) * position.quantity

            # Entry fees have already been charged economically even though
            # the trade is not yet represented by a completed TradeOutcome.
            realized_pnl -= float(position.entry_fees)
            gross_exposure += price * position.quantity

        return VirtualAccountSnapshot(
            timestamp=timestamp,
            equity=self.config.initial_equity + realized_pnl + unrealized_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            gross_exposure=gross_exposure,
            open_positions=len(open_positions),
        )

    def process_candle(self, candle: Candle):
        """Process one completed candle and record the account mark."""
        timestamp = pd.Timestamp(candle.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("session candles must be timezone-aware")

        local_timestamp = timestamp.tz_convert(self.config.market_timezone)
        session_open = pd.Timestamp(
            f"{local_timestamp.date()} {self.config.session_open}",
            tz=self.config.market_timezone,
        )
        session_close = pd.Timestamp(
            f"{local_timestamp.date()} {self.config.session_close}",
            tz=self.config.market_timezone,
        )

        if not (session_open <= local_timestamp <= session_close):
            raise ValueError(
                f"candle timestamp {timestamp.isoformat()} is outside the configured "
                f"session window {self.config.session_open}-{self.config.session_close} "
                f"{self.config.market_timezone}"
            )

        if self._session_date is None:
            self._session_date = local_timestamp.normalize()
        elif local_timestamp.normalize() != self._session_date:
            raise ValueError("virtual session cannot span multiple trading dates")

        prediction = self.orchestrator.process_candle(candle)

        symbol = candle.symbol.strip().upper()
        snapshot = self._account_mark(
            timestamp=timestamp,
            prices={symbol: float(candle.close)},
        )
        self._snapshots.append(snapshot)
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

    def run(self, symbols: Iterable[str] | None = None) -> LivePaperSessionResult:
        """Consume the configured realtime candle stream for one virtual session."""
        expected = (self.orchestrator.config.symbol.strip().upper(),)
        source_symbols = expected if symbols is None else symbols
        requested = tuple(
            symbol.strip().upper()
            for symbol in source_symbols
            if symbol and symbol.strip()
        )
        if requested != expected:
            raise ValueError(
                "virtual session requires exactly the orchestrator's configured symbol"
            )

        self.orchestrator.market_data.start(requested)
        try:
            for candle in self.orchestrator.market_data.run():
                self.process_candle(candle)
        finally:
            self.orchestrator.market_data.stop()

        return self.finalize()

    def finalize(self) -> LivePaperSessionResult:
        """Finalize the paper engine and persist the final account state."""
        result = self.orchestrator.paper_engine.finalize_session()

        if self._snapshots:
            last_timestamp = self._snapshots[-1].timestamp
            final_prices = {
                self.orchestrator.paper_engine.config.symbol.strip().upper():
                float(
                    self._last_candle_close()
                )
            }
            final_snapshot = self._account_mark(
                timestamp=last_timestamp,
                prices=final_prices,
            )
            # Replace the pre-finalization mark at the same decision timestamp
            # so the ledger's final row represents the actual closed account.
            self._snapshots[-1] = final_snapshot

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

    def _last_candle_close(self) -> float:
        """Return the last causal close used by the session."""
        history = getattr(self.orchestrator, "history", None)
        if history is None:
            raise ValueError("cannot finalize account without causal candle history")

        frame = history.frame()
        if frame.empty:
            raise ValueError("cannot finalize account without a processed candle")

        return float(frame["close"].iloc[-1])


__all__ = [
    "VirtualAccountSnapshot",
    "VirtualIntradaySession",
    "VirtualIntradaySessionConfig",
]
