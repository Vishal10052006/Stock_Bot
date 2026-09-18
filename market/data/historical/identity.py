"""Provider-neutral instrument identity contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    """Provider-neutral reference for one exchange-listed security.

    ``isin`` is a security/linkage attribute and must not be assumed to
    uniquely identify one exchange instrument record.
    ``symbol`` is the point-in-time exchange symbol.
    ``exchange`` identifies the listing venue.
    """

    isin: str
    symbol: str
    exchange: str = "NSE"

    def __post_init__(self) -> None:
        """Validate and normalize the instrument identity."""
        if not isinstance(self.isin, str) or not self.isin.strip():
            raise ValueError("isin must be a non-empty string")

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(self.exchange, str) or not self.exchange.strip():
            raise ValueError("exchange must be a non-empty string")

        object.__setattr__(
            self,
            "isin",
            self.isin.strip().upper(),
        )
        object.__setattr__(
            self,
            "symbol",
            self.symbol.strip().upper(),
        )
        object.__setattr__(
            self,
            "exchange",
            self.exchange.strip().upper(),
        )
