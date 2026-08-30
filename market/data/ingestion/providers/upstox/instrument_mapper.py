"""Mapping between Stock Bot symbols and Upstox instrument keys."""

from __future__ import annotations


class UpstoxInstrumentMapper:
    """Resolve internal symbols to provider-specific instrument keys."""

    def __init__(self, mapping: dict[str, str]) -> None:
        """Normalize and validate the provider mapping."""
        normalized = {
            symbol.strip().upper(): instrument_key.strip()
            for symbol, instrument_key in mapping.items()
            if symbol.strip() and instrument_key.strip()
        }
        if not normalized:
            raise ValueError("at least one valid instrument mapping is required")
        self._mapping = normalized

    def instrument_key(self, symbol: str) -> str:
        """Return the Upstox instrument key for an internal symbol."""
        normalized_symbol = symbol.strip().upper()
        try:
            return self._mapping[normalized_symbol]
        except KeyError as exc:
            raise KeyError(f"No Upstox instrument key for symbol: {symbol}") from exc

    def symbols(self) -> tuple[str, ...]:
        """Return configured internal symbols in deterministic order."""
        return tuple(sorted(self._mapping))
