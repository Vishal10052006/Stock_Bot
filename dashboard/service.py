from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any
from .contracts import AgentStatus, DashboardConfig
from .registry import PIPELINE, SOURCE_TO_AGENT, agent_records

def _now(): return datetime.now(timezone.utc).isoformat()

@dataclass
class DashboardService:
    config: DashboardConfig
    monitoring: Any=None
    journal: Any=None
    model_registry: Any=None

    @classmethod
    def from_environment(cls, config=None):
        config=config or DashboardConfig(
            journal_path=os.getenv("STOCK_BOT_MONITORING_JOURNAL","data/monitoring/dashboard.jsonl"),
            environment=os.getenv("STOCK_BOT_ENVIRONMENT","RESEARCH/PAPER"))
        journal=None
        try:
            from monitoring.journal import MonitoringJournal
            journal=MonitoringJournal(config.journal_path)
        except Exception:
            pass
        return cls(config,journal=journal)

    def _events(self):
        if self.journal is None: return []
        try: return [e.to_dict() for e in self.journal.events()]
        except (OSError,ValueError,TypeError): return []

    def _monitoring_payload(self):
        if self.monitoring is None: return {}
        try:
            p=self.monitoring.dashboard() if hasattr(self.monitoring,"dashboard") else {}
            return p if isinstance(p,dict) else {}
        except Exception: return {}

    def agents(self):
        health={str(x.get("component","")).lower():x for x in self._monitoring_payload().get("health",[]) if isinstance(x,dict)}
        events=self._events(); out=[]
        mapping={"HEALTHY":AgentStatus.ACTIVE.value,"DEGRADED":AgentStatus.DEGRADED.value,"UNHEALTHY":AgentStatus.FAILED.value,"UNKNOWN":AgentStatus.UNKNOWN.value}
        for a in agent_records():
            keys=(a["agent_id"].lower(),a["name"].lower(),a["name"].lower().replace("_bot",""))
            obs=next((health[k] for k in keys if k in health),None)
            status=AgentStatus.LOCKED.value if a["locked"] else AgentStatus.WAITING.value
            if obs: status=mapping.get(str(obs.get("status","UNKNOWN")).upper(),AgentStatus.UNKNOWN.value)
            related=[e for e in events if SOURCE_TO_AGENT.get(str(e.get("source","")).lower())==a["agent_id"]]
            out.append({**a,"status":status,"observed":bool(obs),"event_count":len(related),"last_event":related[-1] if related else None})
        return out

    def pipeline(self):
        agents={a["agent_id"]:a for a in self.agents()}; events=self._events(); out=[]
        for sid,name,aid in PIPELINE:
            related=[e for e in events if SOURCE_TO_AGENT.get(str(e.get("source","")).lower())==aid]
            a=agents[aid]
            detail=(str(related[-1].get("event_type")) if related else ("LIVE BROKER LOCKED; PAPER ONLY" if a["status"]=="LOCKED" else "WAITING FOR TELEMETRY"))
            out.append({"stage_id":sid,"name":name,"agent_id":aid,"status":a["status"],"detail":detail,"event_count":len(related)})
        return out

    def models(self):
        if self.model_registry is None: return []
        try: return [self.model_registry.get(v).to_dict() for v in self.model_registry.versions()]
        except Exception: return []

    def events(self,limit=100,source=None,event_type=None,correlation_id=None):
        items=self._events()
        if source: items=[e for e in items if e.get("source")==source]
        if event_type: items=[e for e in items if e.get("event_type")==event_type]
        if correlation_id: items=[e for e in items if e.get("correlation_id")==correlation_id]
        return items[-max(1,min(int(limit),1000)):]

    def decisions(self,correlation_id=None):
        events=self.events(1000,correlation_id=correlation_id); grouped={}
        for e in events: grouped.setdefault(e.get("correlation_id") or e["event_id"],[]).append(e)
        return [{"decision_id":cid,"timestamp":xs[-1]["timestamp"],"event_count":len(xs),"stages":[{"source":e["source"],"event_type":e["event_type"],"severity":e["severity"],"timestamp":e["timestamp"]} for e in xs],"events":xs} for cid,xs in list(grouped.items())[-100:]]

    def learning(self):
        events=self._events(); keys=("OUTCOME","ERROR","EXPERIENCE","DATASET","RETRAIN","OOS","PROMOTION")
        c={k:0 for k in keys}
        for e in events:
            blob=(str(e.get("event_type",""))+" "+str(e.get("source",""))).upper()
            for k in keys:
                if k in blob: c[k]+=1
        return {"stages":[{"stage":i+1,"name":name,"count":c[key]} for i,(name,key) in enumerate((("TRADE OUTCOME","OUTCOME"),("ERROR ANALYSIS","ERROR"),("EXPERIENCE ACCRUAL","EXPERIENCE"),("DATASET UPDATE","DATASET"),("MODEL RETRAINING","RETRAIN"),("OOS / WALK-FORWARD","OOS"),("PROMOTION GATE","PROMOTION")))],"authoritative":False}

    def health(self):
        return {"monitoring":self._monitoring_payload(),"live_trading":"LOCKED","live_order_submission":False,"paper_mode":True,"causality":"ENFORCED","event_count":len(self._events())}

    def overview(self):
        agents=self.agents(); events=self.events(50); s={"registered_agents":len(agents),"active":sum(a["status"]=="ACTIVE" for a in agents),"waiting":sum(a["status"]=="WAITING" for a in agents),"standby":sum(a["status"]=="STANDBY" for a in agents),"locked":sum(a["status"]=="LOCKED" for a in agents),"degraded":sum(a["status"]=="DEGRADED" for a in agents),"failed":sum(a["status"]=="FAILED" for a in agents),"events":len(self._events())}
        return {"timestamp":_now(),"environment":self.config.environment,"causality":"ENFORCED","live_trading":"LOCKED","paper_only":True,"agents":agents,"pipeline":self.pipeline(),"models":self.models(),"learning":self.learning(),"health":self.health(),"events":events,"summary":s}

    def replay(self,correlation_id): return self.events(1000,correlation_id=correlation_id)
