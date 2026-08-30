"""Mapping between Stock Bot symbols and Upstox instrument keys."""

from __future__ import annotations

import json
import os


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

    @classmethod
    def from_env(cls) -> "UpstoxInstrumentMapper":
        """Build an instrument mapper from a JSON environment variable.

        Expected format:
            UPSTOX_INSTRUMENT_MAP='{"RELIANCE":"NSE_EQ|INE002A01018"}'

        Provider-specific identifiers stay in runtime configuration rather
        than being hard-coded into the trading core.
        """
        raw_mapping = os.getenv("UPSTOX_INSTRUMENT_MAP", "").strip()
        if not raw_mapping:
            raise ValueError(
                "UPSTOX_INSTRUMENT_MAP is required for the live market feed"
            )

        try:
            mapping = json.loads(raw_mapping)
        except json.JSONDecodeError as exc:
            raise ValueError("UPSTOX_INSTRUMENT_MAP must contain valid JSON") from exc

        if not isinstance(mapping, dict):
            raise ValueError("UPSTOX_INSTRUMENT_MAP must decode to a JSON object")

        return cls(mapping)

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
