"""MB-01 point-in-time universe and benchmark adapters."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from market.data.historical.point_in_time_universe import build_point_in_time_universe
from market.data.historical.universe import UniversePolicy
from market.data.historical.liquidity import LiquidityPolicy
@dataclass(frozen=True,slots=True)
class MarketUniverse:
    as_of:date; exchange:str; symbols:tuple[str,...]; policy_version:str; source:str
    def __post_init__(self):
        if not isinstance(self.as_of,date): raise TypeError("as_of must be a date")
        s=tuple(sorted(x.strip().upper() for x in self.symbols))
        if any(not x for x in s) or len(s)!=len(set(s)): raise ValueError("symbols must be non-empty and unique")
        object.__setattr__(self,"exchange",self.exchange.strip().upper()); object.__setattr__(self,"policy_version",self.policy_version.strip()); object.__setattr__(self,"source",self.source.strip()); object.__setattr__(self,"symbols",s)
    def contains(self,symbol:str)->bool: return symbol.strip().upper() in self.symbols
@dataclass(frozen=True,slots=True)
class MarketBenchmark:
    symbol:str; exchange:str="NSE"; source:str="configured"
    def __post_init__(self):
        if not self.symbol.strip(): raise ValueError("benchmark symbol must not be empty")
        object.__setattr__(self,"symbol",self.symbol.strip().upper()); object.__setattr__(self,"exchange",self.exchange.strip().upper()); object.__setattr__(self,"source",self.source.strip())
@dataclass(frozen=True,slots=True)
class MarketUniverseConfig:
    benchmark:MarketBenchmark; universe_policy:UniversePolicy; liquidity_policy:LiquidityPolicy; upstox_master_path:str="data/reference/upstox/NSE.json.gz"
def build_market_universe(*,as_of:date,config:MarketUniverseConfig,security_master_adapter=None,bhavcopy_adapter=None):
    result=build_point_in_time_universe(as_of=as_of,liquidity_policy=config.liquidity_policy,universe_policy=config.universe_policy,upstox_master_path=config.upstox_master_path,security_master_adapter=security_master_adapter,bhavcopy_adapter=bhavcopy_adapter)
    return MarketUniverse(as_of=as_of,exchange="NSE",symbols=result.snapshot.symbols,policy_version=result.snapshot.policy_version,source=result.snapshot.source),result
