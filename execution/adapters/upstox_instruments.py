"""Broker-neutral instrument identity and Upstox instrument resolution.

The execution engine should receive a canonical symbol and let the provider
adapter resolve the provider-specific instrument key. Resolution is cached
for the lifetime of the resolver, validates exact matches, and never falls
back to an ambiguous symbol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class InstrumentResolutionError(ValueError):
    """Raised when a symbol cannot be resolved unambiguously."""


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    symbol: str
    instrument_key: str
    exchange: str
    segment: str
    trading_symbol: str
    exchange_token: str | None = None


class InstrumentSearchClient(Protocol):
    """Small provider client contract required by the resolver."""

    def search_instruments(
        self,
        query: str,
        *,
        exchange: str = "NSE",
        segment: str = "EQ",
        limit: int = 20,
    ) -> list[Mapping[str, Any]]:
        ...


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_symbol(value: str) -> str:
    return value.strip().upper()


def _candidate_symbol(record: Mapping[str, Any]) -> str:
    return _text(record.get("trading_symbol") or record.get("symbol")).upper()


def normalize_instrument_record(
    record: Mapping[str, Any],
    *,
    requested_symbol: str,
    exchange: str = "NSE",
    segment: str = "EQ",
) -> InstrumentIdentity:
    instrument_key = _text(record.get("instrument_key"))
    trading_symbol = _text(record.get("trading_symbol") or record.get("symbol"))
    record_exchange = _text(record.get("exchange") or exchange).upper()
    record_segment = _text(record.get("segment") or segment).upper()

    if not instrument_key:
        raise InstrumentResolutionError("provider record missing instrument_key")
    if not trading_symbol:
        raise InstrumentResolutionError("provider record missing trading_symbol")
    if record_exchange != exchange.upper():
        raise InstrumentResolutionError("provider record exchange does not match request")
    if record_segment != segment.upper():
        raise InstrumentResolutionError("provider record segment does not match request")

    return InstrumentIdentity(
        symbol=_normalize_symbol(requested_symbol),
        instrument_key=instrument_key,
        exchange=record_exchange,
        segment=record_segment,
        trading_symbol=trading_symbol.upper(),
        exchange_token=_text(record.get("exchange_token")) or None,
    )


class UpstoxInstrumentResolver:
    """Resolve NSE equity symbols to exact Upstox instrument identities."""

    def __init__(
        self,
        client: InstrumentSearchClient,
        *,
        exchange: str = "NSE",
        segment: str = "EQ",
        search_limit: int = 20,
    ) -> None:
        if search_limit <= 0:
            raise ValueError("search_limit must be positive")
        self.client = client
        self.exchange = exchange.strip().upper()
        self.segment = segment.strip().upper()
        self.search_limit = search_limit
        self._cache: dict[str, InstrumentIdentity] = {}

    def resolve(self, symbol: str) -> InstrumentIdentity:
        normalized = _normalize_symbol(symbol)
        if not normalized:
            raise InstrumentResolutionError("symbol must not be empty")

        cached = self._cache.get(normalized)
        if cached is not None:
            return cached

        records = self.client.search_instruments(
            normalized,
            exchange=self.exchange,
            segment=self.segment,
            limit=self.search_limit,
        )

        exact = [
            record
            for record in records
            if isinstance(record, Mapping)
            and _candidate_symbol(record) == normalized
        ]

        if not exact:
            raise InstrumentResolutionError(
                f"no exact {self.exchange}/{self.segment} instrument found for {normalized}"
            )

        identities = tuple(
            normalize_instrument_record(
                record,
                requested_symbol=normalized,
                exchange=self.exchange,
                segment=self.segment,
            )
            for record in exact
        )

        unique_keys = {item.instrument_key for item in identities}
        if len(unique_keys) != 1:
            raise InstrumentResolutionError(
                f"ambiguous {self.exchange}/{self.segment} instrument for {normalized}"
            )

        identity = identities[0]
        self._cache[normalized] = identity
        return identity

    def resolve_key(self, symbol: str) -> str:
        """Return the provider instrument key for a symbol."""
        return self.resolve(symbol).instrument_key

    def clear_cache(self) -> None:
        self._cache.clear()


__all__ = [
    "InstrumentIdentity",
    "InstrumentResolutionError",
    "InstrumentSearchClient",
    "UpstoxInstrumentResolver",
    "normalize_instrument_record",
]
