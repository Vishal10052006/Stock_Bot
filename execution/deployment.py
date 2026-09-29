"""Phase 26 controlled-deployment gate. It never enables live execution."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json
from datetime import datetime
@dataclass(frozen=True,slots=True)
class DeploymentChecklist:
 readiness_ready: bool; paper_evidence_sufficient: bool; monitoring_validated: bool; kill_switch_validated: bool; broker_sandbox_validated: bool; reconciliation_validated: bool; compliance_current: bool; operator_approval: bool=False; live_lock_override: bool=False
 def failed(self):
  fields=("readiness_ready","paper_evidence_sufficient","monitoring_validated","kill_switch_validated","broker_sandbox_validated","reconciliation_validated","compliance_current","operator_approval")
  return tuple(x for x in fields if not getattr(self,x))
@dataclass(frozen=True,slots=True)
class DeploymentDecision:
 allowed: bool; status: str; failed_gates: tuple[str,...]; reason: str; evaluated_at: datetime; fingerprint: str
class ControlledDeploymentGate:
 VERSION="DEPLOYMENT-v1.0"
 def evaluate(self,checklist,evaluated_at):
  if not isinstance(checklist,DeploymentChecklist): raise TypeError("checklist must be DeploymentChecklist")
  if evaluated_at.tzinfo is None: raise ValueError("evaluated_at must be timezone-aware")
  failed=checklist.failed()
  if checklist.live_lock_override: failed=failed+("live_lock_override_forbidden",)
  failed=failed+("live_execution_locked",)
  reason="Controlled deployment is not authorized; repository live lock remains active."
  payload={"version":self.VERSION,"allowed":False,"status":"BLOCKED","failed_gates":failed,"reason":reason,"evaluated_at":evaluated_at.isoformat()}
  fp=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
  return DeploymentDecision(False,"BLOCKED",failed,reason,evaluated_at,fp)
def assert_live_locked(): raise RuntimeError("live execution is intentionally locked; Phase 26 does not enable broker orders")
__all__=["ControlledDeploymentGate","DeploymentChecklist","DeploymentDecision","assert_live_locked"]