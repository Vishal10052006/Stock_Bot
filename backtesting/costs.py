"""AB-40 configurable transaction-cost model.

The model is deliberately broker-neutral. Exact broker/exchange charges
must be supplied through configuration when the broker layer is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class CostConfig:
    """Configurable transaction-cost assumptions, expressed in bps."""

    brokerage_bps: float = 0.0
    exchange_txn_bps: float = 0.0
    stt_bps: float = 0.0
    gst_bps: float = 0.0
    sebi_bps: float = 0.0
    stamp_duty_bps: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.brokerage_bps,
            self.exchange_txn_bps,
            self.stt_bps,
            self.gst_bps,
            self.sebi_bps,
            self.stamp_duty_bps,
        )

        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("transaction costs must be finite")
        if any(value < 0 for value in values):
            raise ValueError("transaction costs cannot be negative")


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Auditable cost calculation."""

    notional: float
    brokerage: float
    exchange_transaction: float
    stt: float
    gst: float
    sebi: float
    stamp_duty: float

    @property
    def total(self) -> float:
        return (
            self.brokerage
            + self.exchange_transaction
            + self.stt
            + self.gst
            + self.sebi
            + self.stamp_duty
        )


class TransactionCostModel:
    """Deterministic configurable transaction-cost calculator."""

    def __init__(self, config: CostConfig | None = None) -> None:
        self.config = config or CostConfig()

    def calculate(
        self,
        *,
        price: float,
        quantity: float,
    ) -> CostBreakdown:
        if not math.isfinite(float(price)) or price <= 0:
            raise ValueError("price must be positive and finite")

        if not math.isfinite(float(quantity)) or quantity <= 0:
            raise ValueError("quantity must be positive and finite")

        notional = price * quantity
        if not math.isfinite(notional):
            raise ValueError("notional must be finite")

        def bps(value: float) -> float:
            return notional * value / 10_000.0

        brokerage = bps(self.config.brokerage_bps)
        exchange_transaction = bps(self.config.exchange_txn_bps)
        stt = bps(self.config.stt_bps)
        gst = bps(self.config.gst_bps)
        sebi = bps(self.config.sebi_bps)
        stamp_duty = bps(self.config.stamp_duty_bps)

        return CostBreakdown(
            notional=notional,
            brokerage=brokerage,
            exchange_transaction=exchange_transaction,
            stt=stt,
            gst=gst,
            sebi=sebi,
            stamp_duty=stamp_duty,
        )
