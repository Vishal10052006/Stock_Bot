"""Pure portfolio exposure calculations."""

from __future__ import annotations

from portfolio.contracts import PortfolioPosition, PortfolioSnapshot, TradeIntent


def projected_positions(
    snapshot: PortfolioSnapshot,
    intent: TradeIntent,
) -> tuple[PortfolioPosition, ...]:
    """Return the portfolio after applying one trade intent."""
    positions = {position.symbol: position for position in snapshot.positions}
    current = positions.get(intent.symbol)

    delta = intent.quantity if intent.side == "BUY" else -intent.quantity
    new_quantity = (current.quantity if current else 0.0) + delta

    if abs(new_quantity) < 1e-12:
        positions.pop(intent.symbol, None)
    else:
        sector = intent.sector if intent.sector is not None else (current.sector if current else None)
        positions[intent.symbol] = PortfolioPosition(
            symbol=intent.symbol,
            quantity=new_quantity,
            mark_price=intent.price,
            sector=sector,
        )

    return tuple(sorted(positions.values(), key=lambda position: position.symbol))


def projected_snapshot(
    snapshot: PortfolioSnapshot,
    intent: TradeIntent,
) -> PortfolioSnapshot:
    """Build a deterministic projected snapshot without mutation."""
    return PortfolioSnapshot(
        as_of=snapshot.as_of,
        equity=snapshot.equity,
        positions=projected_positions(snapshot, intent),
    )


def sector_exposure_fraction(
    snapshot: PortfolioSnapshot,
    sector: str | None,
) -> float:
    """Return absolute sector exposure divided by equity."""
    if not sector:
        return 0.0
    normalized = sector.strip()
    value = sum(
        abs(position.market_value)
        for position in snapshot.positions
        if position.sector == normalized
    )
    return value / snapshot.equity


def symbol_exposure_fraction(
    snapshot: PortfolioSnapshot,
    symbol: str,
) -> float:
    """Return absolute symbol exposure divided by equity."""
    normalized = symbol.strip().upper()
    value = sum(
        abs(position.market_value)
        for position in snapshot.positions
        if position.symbol == normalized
    )
    return value / snapshot.equity


def position_count(snapshot: PortfolioSnapshot) -> int:
    """Return the number of non-zero positions."""
    return len(snapshot.positions)
