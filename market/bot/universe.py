"""MB-01 point-in-time market universe and benchmark contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from market.data.historical.point_in_time_universe import (
    PointInTimeUniverseResult,
    build_point_in_time_universe,
)
from market.data.historical.universe import UniversePolicy
from market.data.historical.liquidity import LiquidityPolicy


@dataclass(frozen=True, slots=True)
class MarketUniverse:
    """Immutable point-in-time market universe."""

    as_of: date
    exchange: str
    symbols: tuple[str, ...]
    policy_version: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.as_of, date):
            raise TypeError("as_of must be a date")
        if not self.exchange.strip():
            raise ValueError("exchange must not be empty")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")

        normalized = tuple(sorted(symbol.strip().upper() for symbol in self.symbols))
        if any(not symbol for symbol in normalized):
            raise ValueError("symbols must not contain empty values")
        if len(normalized) != len(set(normalized)):
            raise ValueError("symbols must not contain duplicates")

        object.__setattr__(self, "exchange", self.exchange.strip().upper())
        object.__setattr__(self, "policy_version", self.policy_version.strip())
        object.__setattr__(self, "source", self.source.strip())
        object.__setattr__(self, "symbols", normalized)

    def contains(self, symbol: str) -> bool:
        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string")
        return symbol.strip().upper() in self.symbols


@dataclass(frozen=True, slots=True)
class MarketBenchmark:
    """Benchmark identity; descriptive context only."""

    symbol: str
    exchange: str = "NSE"
    source: str = "configured"

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("benchmark symbol must not be empty")
        if not self.exchange.strip():
            raise ValueError("benchmark exchange must not be empty")
        if not self.source.strip():
            raise ValueError("benchmark source must not be empty")

        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "exchange", self.exchange.strip().upper())
        object.__setattr__(self, "source", self.source.strip())


@dataclass(frozen=True, slots=True)
class MarketUniverseConfig:
    """Explicit MB-01 configuration."""

    benchmark: MarketBenchmark
    universe_policy: UniversePolicy
    liquidity_policy: LiquidityPolicy
    upstox_master_path: str = "data/reference/upstox/NSE.json.gz"


def build_market_universe(
    *,
    as_of: date,
    config: MarketUniverseConfig,
    security_master_adapter=None,
    bhavcopy_adapter=None,
) -> tuple[MarketUniverse, PointInTimeUniverseResult]:
    """Build MB-01 through the existing PIT universe engine."""

    result = build_point_in_time_universe(
        as_of=as_of,
        liquidity_policy=config.liquidity_policy,
        universe_policy=config.universe_policy,
        upstox_master_path=config.upstox_master_path,
        security_master_adapter=security_master_adapter,
        bhavcopy_adapter=bhavcopy_adapter,
    )

    universe = MarketUniverse(
        as_of=as_of,
        exchange="NSE",
        symbols=result.snapshot.symbols,
        policy_version=result.snapshot.policy_version,
        source=result.snapshot.source,
    )
    return universe, result
