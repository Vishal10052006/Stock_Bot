import pytest
from execution.broker_gateway import BrokerGatewayConfig, BrokerIntegrationLocked, BrokerMode, LockedBrokerGateway

class Dummy:
    def submit(self, order): raise AssertionError("must not reach adapter")
    def get_order(self, client_order_id): raise AssertionError("must not reach adapter")
    def cancel(self, client_order_id): raise AssertionError("must not reach adapter")
    def positions(self): raise AssertionError("must not reach adapter")

def test_live_config_is_fail_closed():
    with pytest.raises(BrokerIntegrationLocked):
        BrokerGatewayConfig(mode=BrokerMode.LIVE)

def test_live_order_flag_is_fail_closed():
    with pytest.raises(BrokerIntegrationLocked):
        BrokerGatewayConfig(live_order_submission=True)

def test_locked_gateway_never_calls_adapter():
    gateway=LockedBrokerGateway(Dummy())
    with pytest.raises(BrokerIntegrationLocked):
        gateway.submit(None)
    with pytest.raises(BrokerIntegrationLocked):
        gateway.get_order("x")
    with pytest.raises(BrokerIntegrationLocked):
        gateway.cancel("x")
    with pytest.raises(BrokerIntegrationLocked):
        gateway.positions()

def test_gateway_evidence_is_locked():
    evidence=LockedBrokerGateway(Dummy()).evidence()
    assert evidence["mode"]=="SANDBOX"
    assert evidence["live_broker_order_submission"] is False
    assert evidence["broker_network_authority"] is False
