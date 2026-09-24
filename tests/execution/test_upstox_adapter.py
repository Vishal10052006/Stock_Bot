import pandas as pd
import pytest
from execution.adapters.upstox import UpstoxAdapterConfig, UpstoxBrokerAdapter
from execution.engine import OrderRequest, OrderSide, OrderType, OrderStatus
from execution.instruments import Instrument, StaticInstrumentResolver
from execution.trading_execution import ExecutionAuthorization, ExecutionAuthorizationStatus
from trading.strategy.models import StrategyDirection

TS = pd.Timestamp("2026-09-25T10:00:00+05:30")
RESOLVER = StaticInstrumentResolver((Instrument("ITC","NSE","NSE_EQ|INE154A01025",0.05),))

def order(price=150):
    a=ExecutionAuthorization(timestamp=TS,symbol="ITC",direction=StrategyDirection.LONG,status=ExecutionAuthorizationStatus.AUTHORIZED,reason="test",risk_version="risk-v1",approved_quantity=10,approved_notional=1500)
    return OrderRequest("SB-test","decision","ITC",OrderSide.BUY,10,OrderType.LIMIT,price,created_at=TS,authorization=a)

class Client:
    def place_order_v3(self,p): self.payload=p; return {"status":"success","data":{"order_ids":["OID-1"]}}
    def get_order(self,oid): return {"status":"success","data":{"order_id":oid,"quantity":10,"filled_quantity":10,"average_price":150,"status":"complete"}}
    def cancel_order(self,oid): return {"status":"success","data":{"order_id":oid}}
    def positions(self): return {"status":"success","data":{"net_positions":[{"trading_symbol":"ITC","quantity":10,"average_price":150}]}}

def adapter(client=None): return UpstoxBrokerAdapter(UpstoxAdapterConfig(enabled=True,sandbox=True),client or Client(),RESOLVER)

def test_config_is_sandbox_only():
    with pytest.raises(ValueError): UpstoxAdapterConfig(enabled=True,sandbox=False)

def test_slicing_is_rejected_until_child_order_aggregation_exists():
    with pytest.raises(ValueError,match="multiple broker order IDs|single-order"): UpstoxAdapterConfig(enabled=True,sandbox=True,slice_orders=True)

def test_disabled_by_default():
    with pytest.raises(RuntimeError): UpstoxBrokerAdapter(UpstoxAdapterConfig()).submit(order())

def test_enabled_requires_instrument_resolver():
    with pytest.raises(RuntimeError,match="instrument resolver"): UpstoxBrokerAdapter(UpstoxAdapterConfig(enabled=True,sandbox=True),Client()).submit(order())

def test_payload_uses_provider_instrument_token():
    c=Client(); s=adapter(c).submit(order()); assert s.broker_order_id=="OID-1"; assert c.payload["instrument_token"]=="NSE_EQ|INE154A01025"; assert c.payload["transaction_type"]=="BUY"

def test_get_cancel_and_positions_after_submit():
    c=Client(); a=adapter(c); a.submit(order()); assert a.get_order("SB-test").status.value=="FILLED"; assert a.cancel("SB-test").status.value=="CANCELLED"; assert a.positions()[0].quantity==10

def test_refresh_without_broker_identity_fails_closed():
    with pytest.raises(RuntimeError,match="order history|broker order identity"): adapter().get_order("UNKNOWN")

def test_invalid_place_response_fails_closed():
    class Bad(Client):
        def place_order_v3(self,p): return {"status":"success","data":{}}
    with pytest.raises(ValueError,match="order_ids"): adapter(Bad()).submit(order())

def test_malformed_numeric_order_response_fails_closed():
    class Bad(Client):
        def get_order(self,oid): return {"status":"success","data":{"order_id":oid,"quantity":None,"filled_quantity":0,"status":"open"}}
    a=adapter(Bad()); a.submit(order())
    with pytest.raises(ValueError,match="quantity"): a.get_order("SB-test")

def test_limit_price_must_respect_tick_size():
    with pytest.raises(ValueError,match="tick size"): adapter()._payload(order(150.03))

def test_restart_recovery_uses_order_history_tag():
    class RecoveringClient(Client):
        def get_order_history(self,*,tag):
            return {"status":"success","data":[
                {"order_id":"OID-1","quantity":10,"filled_quantity":0,"average_price":0,"status":"put order req received","order_timestamp":"2026-09-25 10:00:00"},
                {"order_id":"OID-1","quantity":10,"filled_quantity":10,"average_price":150,"status":"complete","order_timestamp":"2026-09-25 10:00:01"}]}
    assert adapter(RecoveringClient()).get_order("SB-test").status is OrderStatus.FILLED
