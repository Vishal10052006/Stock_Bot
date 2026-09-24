"""Phase 24 independent latched kill-switch controller."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib, json

@dataclass(frozen=True, slots=True)
class KillSwitchEvent:
    event_id: str
    timestamp: str
    action: str
    reason: str
    source: str
    def __post_init__(self):
        if self.action not in {"ACTIVATE", "CLEAR"}: raise ValueError("invalid kill-switch action")
        for n in ("event_id","timestamp","reason","source"):
            if not getattr(self,n).strip(): raise ValueError(f"{n} must be non-empty")
    @property
    def fingerprint(self):
        p={"event_id":self.event_id,"timestamp":self.timestamp,"action":self.action,"reason":self.reason,"source":self.source}
        return hashlib.sha256(json.dumps(p,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass(frozen=True, slots=True)
class KillSwitchSnapshot:
    active: bool
    reason: str
    activation_count: int
    clear_count: int
    last_event: KillSwitchEvent | None

class KillSwitchController:
    """Fail-closed, latched hard stop."""
    VERSION="KILL-SWITCH-v1.0"
    def __init__(self):
        self._active=True; self._reason="Kill switch starts active until explicitly cleared."
        self._activation_count=1; self._clear_count=0
        self._events=[self._make_event("ACTIVATE",self._reason,"system-start")]
    @staticmethod
    def _make_event(action,reason,source):
        if not isinstance(reason,str) or not reason.strip(): raise ValueError("kill-switch reason must be non-empty")
        if not isinstance(source,str) or not source.strip(): raise ValueError("kill-switch source must be non-empty")
        ts=datetime.now(timezone.utc).isoformat()
        eid=hashlib.sha256(f"{action}|{reason.strip()}|{source.strip()}|{ts}".encode()).hexdigest()
        return KillSwitchEvent(eid,ts,action,reason.strip(),source.strip())
    def activate(self,reason,*,source="operator"):
        e=self._make_event("ACTIVATE",reason,source); self._active=True; self._reason=e.reason
        self._activation_count+=1; self._events.append(e); return self.snapshot()
    def clear(self,*,confirmation,reason,source="operator"):
        if confirmation!="CLEAR KILL SWITCH": raise ValueError("explicit kill-switch confirmation required")
        e=self._make_event("CLEAR",reason,source); self._active=False; self._reason=e.reason
        self._clear_count+=1; self._events.append(e); return self.snapshot()
    def snapshot(self): return KillSwitchSnapshot(self._active,self._reason,self._activation_count,self._clear_count,self._events[-1])
    def events(self): return tuple(self._events)
    def assert_safe(self):
        if self._active: raise RuntimeError(f"kill switch active: {self._reason}")

def kill_switch_active_from_risk_state(state):
    if not hasattr(state,"active"): raise TypeError("state must expose an active property")
    value=getattr(state,"active")
    if not isinstance(value,bool): raise TypeError("state.active must be bool")
    return value

__all__=["KillSwitchController","KillSwitchEvent","KillSwitchSnapshot","kill_switch_active_from_risk_state"]