"""Operational fail-closed safety / kill-switch controller."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib, json
from execution.safety import IndependentSafetyGate, SafetyBlock, SafetyDecision, SafetyState

@dataclass(frozen=True, slots=True)
class SafetyEvent:
    timestamp: datetime
    event: str
    block: SafetyBlock
    reason: str
    fingerprint: str

    @classmethod
    def create(cls, *, timestamp: datetime, event: str, decision: SafetyDecision) -> "SafetyEvent":
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        payload={"timestamp":timestamp.astimezone(timezone.utc).isoformat(),"event":event,
                 "block":decision.block.value,"reason":decision.reason}
        canonical=json.dumps(payload, sort_keys=True, separators=(",",":"))
        return cls(timestamp,event,decision.block,decision.reason,
                   hashlib.sha256(canonical.encode()).hexdigest())

    def to_mapping(self) -> dict[str,str]:
        return {"timestamp":self.timestamp.astimezone(timezone.utc).isoformat(),
                "event":self.event,"block":self.block.value,"reason":self.reason,
                "fingerprint":self.fingerprint,"live_broker_order_submission":"false"}

class SafetyController:
    """Latch safety blocks and expose an explicit, fail-closed reset path."""
    def __init__(self, gate: IndependentSafetyGate | None=None) -> None:
        self._gate=gate or IndependentSafetyGate()
        self._kill_switch_latched=False
        self._events:list[SafetyEvent]=[]

    @property
    def kill_switch_latched(self)->bool:
        return self._kill_switch_latched

    def activate_kill_switch(self, *, timestamp:datetime, reason:str="Operator kill switch activated.")->SafetyDecision:
        self._require_aware(timestamp)
        self._kill_switch_latched=True
        decision=SafetyDecision(False,SafetyBlock.KILL_SWITCH,reason)
        self._events.append(SafetyEvent.create(timestamp=timestamp,event="KILL_SWITCH_ACTIVATED",decision=decision))
        return decision

    def evaluate(self, state:SafetyState, *, timestamp:datetime)->SafetyDecision:
        self._require_aware(timestamp)
        effective=SafetyState(
            kill_switch_active=state.kill_switch_active or self._kill_switch_latched,
            stale_data=state.stale_data,data_quality_ok=state.data_quality_ok,
            session_open=state.session_open,live_execution_enabled=state.live_execution_enabled)
        decision=self._gate.evaluate(effective)
        self._events.append(SafetyEvent.create(timestamp=timestamp,
            event="SAFETY_BLOCKED" if not decision.allowed else "SAFETY_PASSED",decision=decision))
        return decision

    def reset_kill_switch(self, *, state:SafetyState, timestamp:datetime)->SafetyDecision:
        self._require_aware(timestamp)
        if state.kill_switch_active:
            decision=SafetyDecision(False,SafetyBlock.KILL_SWITCH,
                                    "Reset refused while kill_switch_active is asserted.")
        else:
            decision=self._gate.evaluate(SafetyState(
                kill_switch_active=False,stale_data=state.stale_data,
                data_quality_ok=state.data_quality_ok,session_open=state.session_open,
                live_execution_enabled=state.live_execution_enabled))
        if decision.allowed:
            self._kill_switch_latched=False
            event="KILL_SWITCH_RESET"
        else:
            event="KILL_SWITCH_RESET_REFUSED"
        self._events.append(SafetyEvent.create(timestamp=timestamp,event=event,decision=decision))
        return decision

    def events(self)->tuple[SafetyEvent,...]:
        return tuple(self._events)

    def evidence(self)->dict[str,object]:
        return {"kill_switch_latched":self._kill_switch_latched,
                "event_count":len(self._events),
                "events":[e.to_mapping() for e in self._events],
                "live_broker_order_submission":False}

    @staticmethod
    def _require_aware(timestamp:datetime)->None:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

__all__=["SafetyController","SafetyEvent"]
