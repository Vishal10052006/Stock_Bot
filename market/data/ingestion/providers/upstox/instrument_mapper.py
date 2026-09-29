"""Mapping between Stock Bot symbols and Upstox instrument keys."""

from __future__ import annotations

import gzip
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UpstoxInstrumentIdentity:
    """Stable provider identity for one configured instrument."""

    symbol: str
    instrument_key: str
    isin: str

    def __post_init__(self) -> None:
        """Validate the provider identity contract."""
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if (
            not isinstance(self.instrument_key, str)
            or not self.instrument_key.strip()
        ):
            raise ValueError(
                "instrument_key must be a non-empty string"
            )

        if not isinstance(self.isin, str) or not self.isin.strip():
            raise ValueError("isin must be a non-empty string")

        object.__setattr__(
            self,
            "symbol",
            self.symbol.strip().upper(),
        )
        object.__setattr__(
            self,
            "instrument_key",
            self.instrument_key.strip(),
        )
        object.__setattr__(
            self,
            "isin",
            self.isin.strip().upper(),
        )


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
    def from_local_master(
        cls,
        path: str | os.PathLike[str] = "data/reference/upstox/NSE.json.gz",
    ) -> "UpstoxInstrumentMapper":
        """Build a symbol mapper from the canonical local Upstox NSE master.

        The master is treated as runtime reference data, not as model input.
        Ambiguous equity symbols fail closed instead of choosing arbitrarily.
        NIFTY50 is handled as the verified NSE index identity.
        """
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"Upstox instrument master not found: {source}")

        opener = gzip.open if source.suffix == ".gz" else open
        with opener(source, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError("Upstox instrument master must contain a JSON list")

        mapping: dict[str, str] = {"NIFTY50": "NSE_INDEX|Nifty 50"}
        for item in payload:
            if not isinstance(item, dict):
                continue
            if item.get("segment") != "NSE_EQ" or item.get("instrument_type") != "EQ":
                continue
            symbol = str(item.get("trading_symbol", item.get("symbol", ""))).strip().upper()
            key = str(item.get("instrument_key", "")).strip()
            if not symbol or not key:
                continue
            previous = mapping.get(symbol)
            if previous is not None and previous != key:
                raise ValueError(f"ambiguous Upstox symbol mapping: {symbol}")
            mapping[symbol] = key

        if len(mapping) <= 1:
            raise ValueError("Upstox instrument master contained no NSE equities")
        return cls(mapping)

    @classmethod
    def from_env(
        cls,
        env_var: str = "UPSTOX_INSTRUMENT_MAP",
    ) -> "UpstoxInstrumentMapper":
        """Build an instrument mapper from a JSON environment variable.

        Expected format:
            UPSTOX_INSTRUMENT_MAP='{"RELIANCE":"NSE_EQ|INE002A01018"}'

        Provider-specific identifiers stay in runtime configuration rather
        than being hard-coded into the trading core.
        """
        if not isinstance(env_var, str) or not env_var.strip():
            raise ValueError("env_var must be a non-empty string")

        env_var = env_var.strip()

        raw_mapping = os.getenv(env_var, "").strip()
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

    def identity(self, symbol: str) -> UpstoxInstrumentIdentity:
        """Return the provider identity for an internal symbol."""
        normalized_symbol = symbol.strip().upper()

        instrument_key = self.instrument_key(normalized_symbol)

        parts = instrument_key.split("|", 1)

        if len(parts) != 2 or not parts[1].strip():
            raise ValueError("Upstox instrument key must contain a provider segment and identity")
        if parts[0] == "NSE_INDEX" and normalized_symbol == "NIFTY50":
            return UpstoxInstrumentIdentity(
                symbol=normalized_symbol,
                instrument_key=instrument_key,
                isin=parts[1].strip().upper(),
            )
        if parts[0] != "NSE_EQ":
            raise ValueError("NSE equity instrument key must use the NSE_EQ segment")
        return UpstoxInstrumentIdentity(
            symbol=normalized_symbol,
            instrument_key=instrument_key,
            isin=parts[1].strip().upper(),
        )
