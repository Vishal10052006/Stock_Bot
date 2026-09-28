"""Mapping between Stock Bot symbols and Upstox instrument keys."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UpstoxInstrumentIdentity:
    """Stable provider identity for one configured instrument."""

    symbol: str
    instrument_key: str
    isin: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        if not isinstance(self.instrument_key, str) or not self.instrument_key.strip():
            raise ValueError("instrument_key must be a non-empty string")
        if not isinstance(self.isin, str) or not self.isin.strip():
            raise ValueError("isin must be a non-empty string")

        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "instrument_key", self.instrument_key.strip())
        object.__setattr__(self, "isin", self.isin.strip().upper())


class UpstoxInstrumentMapper:
    """Resolve internal symbols to provider-specific instrument keys."""

    def __init__(self, mapping: dict[str, str]) -> None:
        if not isinstance(mapping, dict):
            raise ValueError("instrument mapping must be a JSON object")

        normalized: dict[str, str] = {}
        for symbol, instrument_key in mapping.items():
            if not isinstance(symbol, str) or not isinstance(instrument_key, str):
                raise ValueError("instrument mapping keys and values must be strings")

            normalized_symbol = symbol.strip().upper()
            normalized_key = instrument_key.strip()

            if not normalized_symbol or not normalized_key:
                continue

            if normalized_symbol in normalized and normalized[normalized_symbol] != normalized_key:
                raise ValueError(
                    f"conflicting Upstox instrument keys for symbol: {normalized_symbol}"
                )

            normalized[normalized_symbol] = normalized_key

        if not normalized:
            raise ValueError("at least one valid instrument mapping is required")

        self._mapping = normalized

    @classmethod
    def from_env(cls, env_var: str = "UPSTOX_INSTRUMENT_MAP") -> "UpstoxInstrumentMapper":
        """Build an instrument mapper from a JSON environment variable."""
        if not isinstance(env_var, str) or not env_var.strip():
            raise ValueError("env_var must be a non-empty string")

        raw_mapping = os.getenv(env_var.strip(), "").strip()
        if not raw_mapping:
            raise ValueError(
                f"{env_var.strip()} is required for the Upstox market-data feed"
            )

        try:
            mapping = json.loads(raw_mapping)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{env_var.strip()} must contain valid JSON") from exc

        if not isinstance(mapping, dict):
            raise ValueError(f"{env_var.strip()} must decode to a JSON object")

        return cls(mapping)

    def instrument_key(self, symbol: str) -> str:
        """Return the Upstox instrument key for an internal symbol."""
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        normalized_symbol = symbol.strip().upper()
        try:
            return self._mapping[normalized_symbol]
        except KeyError as exc:
            raise KeyError(f"No Upstox instrument key for symbol: {symbol}") from exc

    def symbols(self) -> tuple[str, ...]:
        """Return configured internal symbols in deterministic order."""
        return tuple(sorted(self._mapping))

    def identity(self, symbol: str) -> UpstoxInstrumentIdentity:
        """Return the provider identity for an NSE equity symbol."""
        normalized_symbol = symbol.strip().upper()
        instrument_key = self.instrument_key(normalized_symbol)
        parts = instrument_key.split("|", 1)

        if len(parts) != 2 or parts[0] != "NSE_EQ" or not parts[1].strip():
            raise ValueError(
                "NSE equity instrument key must have the format NSE_EQ|<ISIN>"
            )

        return UpstoxInstrumentIdentity(
            symbol=normalized_symbol,
            instrument_key=instrument_key,
            isin=parts[1].strip().upper(),
        )

    def evidence(self) -> dict[str, object]:
        """Return non-secret deterministic mapping evidence."""
        return {
            "provider": "upstox",
            "instrument_count": len(self._mapping),
            "symbols": self.symbols(),
            "instrument_keys": tuple(
                self._mapping[symbol] for symbol in self.symbols()
            ),
            "live_broker_order_submission": False,
        }

    def fingerprint(self) -> str:
        """Fingerprint the configured provider instrument universe."""
        payload = json.dumps(
            self.evidence(),
            sort_keys=True,
            separators=(",", ":"),
            default=list,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


__all__ = ["UpstoxInstrumentIdentity", "UpstoxInstrumentMapper"]
