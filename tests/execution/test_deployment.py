import pandas as pd
import pytest
from execution.deployment import ControlledDeploymentGate,DeploymentChecklist,assert_live_locked
def checklist(**o):
 v=dict(readiness_ready=True,paper_evidence_sufficient=True,monitoring_validated=True,kill_switch_validated=True,broker_sandbox_validated=True,reconciliation_validated=True,compliance_current=True,operator_approval=True); v.update(o); return DeploymentChecklist(**v)
def test_phase26_never_authorizes_live_execution():
 d=ControlledDeploymentGate().evaluate(checklist(),pd.Timestamp("2026-09-25T10:00:00Z").to_pydatetime()); assert not d.allowed and d.status=="BLOCKED" and "live_execution_locked" in d.failed_gates and len(d.fingerprint)==64
def test_missing_prerequisite_is_reported():
 d=ControlledDeploymentGate().evaluate(checklist(paper_evidence_sufficient=False),pd.Timestamp("2026-09-25T10:00:00Z").to_pydatetime()); assert "paper_evidence_sufficient" in d.failed_gates
def test_lock_override_is_forbidden():
 d=ControlledDeploymentGate().evaluate(checklist(live_lock_override=True),pd.Timestamp("2026-09-25T10:00:00Z").to_pydatetime()); assert "live_lock_override_forbidden" in d.failed_gates
def test_live_lock_function_fails_closed():
 with pytest.raises(RuntimeError,match="intentionally locked"): assert_live_locked()
def test_timezone_required():
 with pytest.raises(ValueError,match="timezone-aware"): ControlledDeploymentGate().evaluate(checklist(),pd.Timestamp("2026-09-25T10:00:00").to_pydatetime())