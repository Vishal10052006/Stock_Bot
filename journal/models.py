"""AB-45 immutable trade-journal models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json

from trading.paper.lifecycle import TradeOutcome


@dataclass(frozen=True, slots=True)
class TradeJournalRecord:
    """Immutable persisted representation of a completed trade."""

    journal_id: str
    symbol: str
    direction: str

    entry_time: datetime
    exit_time: datetime

    entry_price: float
    exit_price: float
    quantity: float

    gross_pnl: float
    fees: float
    slippage_cost: float
    net_pnl: float

    holding_minutes: float
    mae: float
    mfe: float

    @classmethod
    def from_trade_outcome(
        cls,
        outcome: TradeOutcome,
    ) -> "TradeJournalRecord":
        """Create a journal record from the canonical trade outcome."""

        if not isinstance(outcome, TradeOutcome):
            raise TypeError(
                "outcome must be a TradeOutcome"
            )

        symbol = str(outcome.symbol).upper()

        if not symbol:
            raise ValueError(
                "trade symbol must not be empty"
            )

        direction = outcome.direction.value

        payload = {
            "symbol": symbol,
            "direction": direction,
            "entry_time": outcome.entry_time.isoformat(),
            "exit_time": outcome.exit_time.isoformat(),
            "entry_price": float(outcome.entry_price),
            "exit_price": float(outcome.exit_price),
            "quantity": float(outcome.quantity),
            "gross_pnl": float(outcome.gross_pnl),
            "fees": float(outcome.fees),
            "slippage_cost": float(
                outcome.slippage_cost
            ),
            "net_pnl": float(outcome.net_pnl),
            "holding_minutes": float(
                outcome.holding_minutes
            ),
            "mae": float(outcome.mae),
            "mfe": float(outcome.mfe),
        }

        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        journal_id = hashlib.sha256(
            canonical
        ).hexdigest()

        return cls(
            journal_id=journal_id,
            symbol=symbol,
            direction=direction,
            entry_time=outcome.entry_time,
            exit_time=outcome.exit_time,
            entry_price=float(outcome.entry_price),
            exit_price=float(outcome.exit_price),
            quantity=float(outcome.quantity),
            gross_pnl=float(outcome.gross_pnl),
            fees=float(outcome.fees),
            slippage_cost=float(
                outcome.slippage_cost
            ),
            net_pnl=float(outcome.net_pnl),
            holding_minutes=float(
                outcome.holding_minutes
            ),
            mae=float(outcome.mae),
            mfe=float(outcome.mfe),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""

        data = asdict(self)

        data["entry_time"] = self.entry_time.isoformat()
        data["exit_time"] = self.exit_time.isoformat()

        return data

    def to_json(self) -> str:
        """Return deterministic JSON representation."""

        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, object],
    ) -> "TradeJournalRecord":
        """Restore a journal record from persisted data."""

        required = {
            "journal_id",
            "symbol",
            "direction",
            "entry_time",
            "exit_time",
            "entry_price",
            "exit_price",
            "quantity",
            "gross_pnl",
            "fees",
            "slippage_cost",
            "net_pnl",
            "holding_minutes",
            "mae",
            "mfe",
        }

        missing = required.difference(data)

        if missing:
            raise ValueError(
                "journal record missing required fields: "
                f"{sorted(missing)}"
            )

        return cls(
            journal_id=str(data["journal_id"]),
            symbol=str(data["symbol"]),
            direction=str(data["direction"]),
            entry_time=datetime.fromisoformat(
                str(data["entry_time"])
            ),
            exit_time=datetime.fromisoformat(
                str(data["exit_time"])
            ),
            entry_price=float(data["entry_price"]),
            exit_price=float(data["exit_price"]),
            quantity=float(data["quantity"]),
            gross_pnl=float(data["gross_pnl"]),
            fees=float(data["fees"]),
            slippage_cost=float(
                data["slippage_cost"]
            ),
            net_pnl=float(data["net_pnl"]),
            holding_minutes=float(
                data["holding_minutes"]
            ),
            mae=float(data["mae"]),
            mfe=float(data["mfe"]),
        )
