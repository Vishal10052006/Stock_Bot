from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
MONITORING_API_VERSION="monitoring-v1"
@dataclass(frozen=True, slots=True)
class MonitoringContract:
    api_version: str=MONITORING_API_VERSION
    authority: str="OBSERVATION_ONLY"
    domains: tuple[str,...]=("system","data","features","model","regime","strategy","risk","execution","alerts")
    def as_dict(self)->Mapping[str,Any]:
        return {"api_version":self.api_version,"authority":self.authority,"domains":list(self.domains)}
