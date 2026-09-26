from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

class AgentStatus(str, Enum):
    ACTIVE="ACTIVE"; WAITING="WAITING"; STANDBY="STANDBY"; DEGRADED="DEGRADED"
    FAILED="FAILED"; LOCKED="LOCKED"; UNKNOWN="UNKNOWN"

@dataclass(frozen=True, slots=True)
class AgentDefinition:
    agent_id: str
    name: str
    role: str
    input_contract: str
    output_contract: str
    locked: bool=False
    order: int=0
    def to_dict(self)->dict[str,Any]: return asdict(self)

@dataclass(frozen=True, slots=True)
class DashboardConfig:
    host: str="127.0.0.1"
    port: int=8765
    journal_path: str="data/monitoring/dashboard.jsonl"
    refresh_seconds: float=1.0
    environment: str="RESEARCH/PAPER"
    def __post_init__(self)->None:
        if not self.host.strip(): raise ValueError("host must not be empty")
        if not 1<=self.port<=65535: raise ValueError("invalid port")
        if self.refresh_seconds<=0: raise ValueError("refresh_seconds must be positive")
