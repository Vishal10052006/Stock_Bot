"""Local Upstox instrument-master loader and symbol resolver.

The Upstox BOD instrument JSON is the preferred source for full-universe
resolution. It can be refreshed daily and indexed locally so execution does
not depend on a per-order search request.
"""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import json
from pathlib import Path
from typing import Any, Mapping


class InstrumentMasterError(RuntimeError):
    """Raised when an instrument-master file cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class MasterInstrument:
    symbol: str
    instrument_key: str
    exchange: str
    segment: str
    instrument_type: str
    trading_symbol: str
    isin: str | None = None
    exchange_token: str | None = None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _symbol(value: str) -> str:
    return value.strip().upper()


def _load_json(path: Path) -> Any:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                return json.load(handle)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise InstrumentMasterError(f"unable to read instrument master: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InstrumentMasterError(f"invalid JSON instrument master: {path}") from exc


def load_nse_equity_master(path: str | Path) -> tuple[MasterInstrument, ...]:
    """Load and validate NSE equity instruments from a Upstox JSON/BOD file."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"instrument master not found: {source}")

    payload = _load_json(source)
    if not isinstance(payload, list):
        raise InstrumentMasterError("instrument master must contain a JSON list")

    instruments: list[MasterInstrument] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue

        segment = _text(item.get("segment")).upper()
        instrument_type = _text(item.get("instrument_type")).upper()
        exchange = _text(item.get("exchange")).upper()
        instrument_key = _text(item.get("instrument_key"))
        trading_symbol = _text(item.get("trading_symbol"))
        isin = _text(item.get("isin")) or None
        exchange_token = _text(item.get("exchange_token")) or None

        if segment != "NSE_EQ" or instrument_type != "EQ" or exchange != "NSE":
            continue
        if not instrument_key or not trading_symbol:
            continue

        instruments.append(
            MasterInstrument(
                symbol=trading_symbol.upper(),
                instrument_key=instrument_key,
                exchange=exchange,
                segment=segment,
                instrument_type=instrument_type,
                trading_symbol=trading_symbol.upper(),
                isin=isin.upper() if isin else None,
                exchange_token=exchange_token,
            )
        )

    if not instruments:
        raise InstrumentMasterError("instrument master contains no NSE equity records")

    return tuple(instruments)


class LocalUpstoxInstrumentResolver:
    """Resolve symbols against a validated local Upstox instrument master."""

    def __init__(self, instruments: tuple[MasterInstrument, ...]) -> None:
        if not instruments:
            raise ValueError("instruments must not be empty")

        by_symbol: dict[str, MasterInstrument] = {}
        for item in instruments:
            key = _symbol(item.symbol)
            previous = by_symbol.get(key)
            if previous is not None and previous.instrument_key != item.instrument_key:
                raise InstrumentMasterError(
                    f"ambiguous local instrument master for {key}"
                )
            by_symbol[key] = item

        self._by_symbol = by_symbol

    @classmethod
    def from_file(cls, path: str | Path) -> "LocalUpstoxInstrumentResolver":
        return cls(load_nse_equity_master(path))

    def resolve(self, symbol: str) -> MasterInstrument:
        normalized = _symbol(symbol)
        if not normalized:
            raise ValueError("symbol must not be empty")

        try:
            return self._by_symbol[normalized]
        except KeyError as exc:
            raise KeyError(f"no NSE_EQ instrument found for {normalized}") from exc

    def resolve_key(self, symbol: str) -> str:
        return self.resolve(symbol).instrument_key

    def __len__(self) -> int:
        return len(self._by_symbol)


__all__ = [
    "InstrumentMasterError",
    "LocalUpstoxInstrumentResolver",
    "MasterInstrument",
    "load_nse_equity_master",
]
