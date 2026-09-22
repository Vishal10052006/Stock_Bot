"""MB-01 adapter around the existing point-in-time universe engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from market.data.historical.liquidity import LiquidityPolicy
from market.data.historical.point_in_time_universe import (
    PointInTimeUniverseResult,
    build_point_in_time_universe,
)
from market.data.historical.universe import UniversePolicy


@dataclass(frozen=True, slots=True)
class MarketBenchmark:
    symbol: str
    exchange: str = "NSE"
    source: str = "configured"

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("benchmark symbol must not be empty")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "exchange", self.exchange.strip().upper())


@dataclass(frozen=True, slots=True)
class MarketUniverseConfig:
    benchmark: MarketBenchmark
    universe_policy: UniversePolicy
    liquidity_policy: LiquidityPolicy
    upstox_master_path: str = "data/reference/upstox/NSE.json.gz"


def build_market_universe(*, as_of: date, config: MarketUniverseConfig,
                          security_master_adapter=None, bhavcopy_adapter=None
                          ) -> tuple[tuple[str, ...], PointInTimeUniverseResult]:
    """Build a PIT universe using the project's authoritative infrastructure."""
    result = build_point_in_time_universe(
        as_of=as_of,
        liquidity_policy=config.liquidity_policy,
        universe_policy=config.universe_policy,
        upstox_master_path=config.upstox_master_path,
        security_master_adapter=security_master_adapter,
        bhavcopy_adapter=bhavcopy_adapter,
    )
    return result.snapshot.symbols, result
