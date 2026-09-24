import pytest
from execution.kill_switch import KillSwitchController, kill_switch_active_from_risk_state
from trading.risk.kill_switch import KillSwitchState

def test_kill_switch_fails_closed_on_startup():
    s=KillSwitchController().snapshot(); assert s.active and s.activation_count==1 and s.clear_count==0
def test_kill_switch_activation_is_latched():
    k=KillSwitchController(); k.clear(confirmation="CLEAR KILL SWITCH",reason="paper test"); s=k.activate("abnormal latency")
    assert s.active and "abnormal latency" in s.reason
def test_clear_requires_explicit_confirmation():
    k=KillSwitchController()
    with pytest.raises(ValueError,match="explicit"): k.clear(confirmation="yes",reason="operator request")
    assert k.snapshot().active
def test_clear_is_audited():
    k=KillSwitchController(); k.clear(confirmation="CLEAR KILL SWITCH",reason="paper validation",source="test")
    s=k.snapshot(); assert not s.active and s.clear_count==1 and s.last_event.action=="CLEAR" and len(s.last_event.fingerprint)==64
def test_assert_safe_fails_closed():
    with pytest.raises(RuntimeError,match="kill switch active"): KillSwitchController().assert_safe()
def test_risk_adapter_is_read_only():
    assert kill_switch_active_from_risk_state(KillSwitchState()) is False
    assert kill_switch_active_from_risk_state(KillSwitchState(model_degradation=True)) is True
def test_invalid_risk_adapter_fails_closed():
    with pytest.raises(TypeError): kill_switch_active_from_risk_state(object())