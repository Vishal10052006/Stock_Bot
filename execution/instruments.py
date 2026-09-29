"""Provider-neutral instrument identity and deterministic mapping contract."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Protocol

@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    exchange: str
    instrument_token: str
    tick_size: float
    lot_size: int = 1
    def __post_init__(self):
        if not self.symbol.strip() or not self.exchange.strip() or not self.instrument_token.strip():
            raise ValueError("instrument identity fields must be non-empty")
        if not isfinite(self.tick_size) or self.tick_size <= 0:
            raise ValueError("tick_size must be finite and positive")
        if self.lot_size <= 0:
            raise ValueError("lot_size must be positive")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "exchange", self.exchange.strip().upper())

class InstrumentResolver(Protocol):
    def resolve(self, symbol: str) -> Instrument: ...

@dataclass(frozen=True, slots=True)
class StaticInstrumentResolver:
    instruments: tuple[Instrument, ...]
    def __post_init__(self):
        symbols = [x.symbol for x in self.instruments]
        if len(set(symbols)) != len(symbols):
            raise ValueError("duplicate instrument symbols")
    def resolve(self, symbol: str) -> Instrument:
        key = symbol.strip().upper()
        for instrument in self.instruments:
            if instrument.symbol == key:
                return instrument
        raise KeyError(f"instrument mapping not found: {key}")
