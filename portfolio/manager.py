"""Deterministic portfolio-level policy engine.

Boundary:
    Strategy -> Portfolio -> Risk -> Safety -> Execution

Portfolio does not calculate risk-first size, authorize execution, or call a
broker.
"""

from __future__ import annotations

from portfolio.contracts import (
    PortfolioAction,
    PortfolioDecision,
    PortfolioLimits,
    PortfolioSnapshot,
    TradeIntent,
)
from portfolio.transition import classify_position_transition
from portfolio.exposure import (
    position_count,
    projected_snapshot,
    sector_exposure_fraction,
    symbol_exposure_fraction,
)


class PortfolioManager:
    """Evaluate aggregate portfolio constraints."""

    VERSION = "PORTFOLIO-v1.0"

    def __init__(self, limits: PortfolioLimits) -> None:
        self.limits = limits

    def evaluate(
        self,
        snapshot: PortfolioSnapshot,
        intent: TradeIntent,
    ) -> PortfolioDecision:
        """Evaluate one proposed trade against explicit portfolio policies."""
        projected = projected_snapshot(snapshot, intent)
        projected_count = position_count(projected)
        existing_position = next((p for p in snapshot.positions if p.symbol == intent.symbol), None)
        transition = classify_position_transition(existing_position, intent).transition

        # For an existing symbol, sector may already be part of portfolio
        # state. Preserve that authoritative context when the intent omits it.
        projected_position = next(
            (
                position
                for position in projected.positions
                if position.symbol == intent.symbol
            ),
            None,
        )
        sector = (
            intent.sector
            if intent.sector is not None
            else (projected_position.sector if projected_position is not None else None)
        )

        checks = (
            self._check_position_count(projected_count),
            self._check_gross_exposure(projected),
            self._check_symbol_exposure(projected, intent.symbol),
            self._check_sector_exposure(projected, sector),
        )

        for reason_code, reason in checks:
            if reason_code:
                return self._decision(
                    snapshot=snapshot,
                    projected=projected,
                    intent=intent,
                    action=PortfolioAction.REJECT,
                    reason_code=reason_code,
                    reason=reason,
                    position_transition=transition,
                )

        return self._decision(
            snapshot=snapshot,
            projected=projected,
            intent=intent,
            action=PortfolioAction.APPROVE,
            reason_code="PORTFOLIO_OK",
            reason="Portfolio-level constraints passed.",
            position_transition=transition,
        )

    def _check_position_count(self, projected_count: int) -> tuple[str | None, str]:
        limit = self.limits.max_positions
        if limit is not None and projected_count > limit:
            return "MAX_POSITIONS", f"Projected position count {projected_count} exceeds limit {limit}."
        return None, ""

    def _check_gross_exposure(self, projected: PortfolioSnapshot) -> tuple[str | None, str]:
        limit = self.limits.max_gross_exposure_fraction
        if limit is not None and projected.gross_exposure_fraction > limit + 1e-12:
            return (
                "MAX_GROSS_EXPOSURE",
                f"Projected gross exposure {projected.gross_exposure_fraction:.6f} exceeds limit {limit:.6f}.",
            )
        return None, ""

    def _check_symbol_exposure(self, projected: PortfolioSnapshot, symbol: str) -> tuple[str | None, str]:
        limit = self.limits.max_symbol_exposure_fraction
        if limit is not None:
            exposure = symbol_exposure_fraction(projected, symbol)
            if exposure > limit + 1e-12:
                return (
                    "MAX_SYMBOL_EXPOSURE",
                    f"Projected symbol exposure {exposure:.6f} exceeds limit {limit:.6f}.",
                )
        return None, ""

    def _check_sector_exposure(self, projected: PortfolioSnapshot, sector: str | None) -> tuple[str | None, str]:
        limit = self.limits.max_sector_exposure_fraction
        if limit is not None and sector:
            exposure = sector_exposure_fraction(projected, sector)
            if exposure > limit + 1e-12:
                return (
                    "MAX_SECTOR_EXPOSURE",
                    f"Projected sector exposure {exposure:.6f} exceeds limit {limit:.6f}.",
                )
        return None, ""

    @staticmethod
    def _decision(
        *,
        snapshot: PortfolioSnapshot,
        projected: PortfolioSnapshot,
        intent: TradeIntent,
        action: PortfolioAction,
        reason_code: str,
        reason: str,
        position_transition,
    ) -> PortfolioDecision:
        return PortfolioDecision(
            action=action,
            symbol=intent.symbol,
            decision_id=intent.decision_id,
            reason_code=reason_code,
            reason=reason,
            current_gross_exposure_fraction=snapshot.gross_exposure_fraction,
            projected_gross_exposure_fraction=projected.gross_exposure_fraction,
            projected_position_count=position_count(projected),
            position_transition=position_transition,
        )
