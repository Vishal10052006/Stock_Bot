import pandas as pd
import pytest
from execution.safety import SafetyBlock, SafetyState
from execution.safety_controller import SafetyController

def ts(minutes=0):
    return pd.Timestamp("2026-09-24T10:00:00Z")+pd.Timedelta(minutes=minutes)

def test_kill_switch_latches_until_safe_explicit_reset():
    c=SafetyController()
    assert c.activate_kill_switch(timestamp=ts()).block is SafetyBlock.KILL_SWITCH
    assert c.kill_switch_latched
    assert c.evaluate(SafetyState(live_execution_enabled=True),timestamp=ts(1)).block is SafetyBlock.KILL_SWITCH
    refused=c.reset_kill_switch(state=SafetyState(stale_data=True,live_execution_enabled=True),timestamp=ts(2))
    assert refused.block is SafetyBlock.STALE_DATA and c.kill_switch_latched
    reset=c.reset_kill_switch(state=SafetyState(live_execution_enabled=True),timestamp=ts(3))
    assert reset.allowed and not c.kill_switch_latched

def test_reset_refuses_asserted_source_kill_switch():
    c=SafetyController(); c.activate_kill_switch(timestamp=ts())
    d=c.reset_kill_switch(state=SafetyState(kill_switch_active=True,live_execution_enabled=True),timestamp=ts(1))
    assert d.block is SafetyBlock.KILL_SWITCH and c.kill_switch_latched

def test_controller_requires_timezone_aware_events():
    with pytest.raises(ValueError,match="timezone-aware"):
        SafetyController().activate_kill_switch(timestamp=pd.Timestamp("2026-09-24 10:00"))

def test_evidence_is_broker_free_and_fingerprinted():
    c=SafetyController(); c.activate_kill_switch(timestamp=ts())
    e=c.evidence()
    assert e["live_broker_order_submission"] is False
    assert e["event_count"]==1
    assert len(e["events"][0]["fingerprint"])==64
