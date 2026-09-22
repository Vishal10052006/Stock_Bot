"""Stable Market Bot contracts and authority boundaries."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from typing import Any,Mapping
@dataclass(frozen=True,slots=True)
class MarketBotInput:
    data:Any; benchmark:str; as_of:datetime|None=None; universe:tuple[str,...]=(); data_version:str="unknown"; feature_version:str="market-bot-v1"; provenance:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if not self.benchmark.strip(): raise ValueError("benchmark must not be empty")
        if self.as_of is not None and self.as_of.tzinfo is None: raise ValueError("as_of must be timezone-aware")
        object.__setattr__(self,"benchmark",self.benchmark.strip().upper())
        object.__setattr__(self,"universe",tuple(sorted({s.strip().upper() for s in self.universe if s.strip()})))
@dataclass(frozen=True,slots=True)
class MarketState:
    timestamp:datetime; benchmark:str; regime:str|None=None; regime_probability:float|None=None; trend_state:str|None=None; trend_strength:float|None=None; range_state:str|None=None; volatility_state:str|None=None; breadth_state:str|None=None; sector_state:str|None=None; rotation_state:str|None=None; correlation_state:str|None=None; liquidity_state:str|None=None; strength_state:str|None=None; transition_state:str|None=None; quality:float|None=None; availability:str="AVAILABLE"; provenance:str="market_bot"; version:str="market-bot-v1"
    def __post_init__(self):
        if self.timestamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        if not self.benchmark.strip(): raise ValueError("benchmark must not be empty")
        for n in ("regime_probability","trend_strength","quality"):
            v=getattr(self,n)
            if v is not None and not 0<=float(v)<=1: raise ValueError(f"{n} must be within [0,1]")
        if self.availability not in {"AVAILABLE","PARTIAL","UNAVAILABLE"}: raise ValueError("invalid availability")
        object.__setattr__(self,"benchmark",self.benchmark.strip().upper())
MarketContext=MarketState
