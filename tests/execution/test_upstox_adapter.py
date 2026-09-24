import pytest
import pandas as pd
from execution.adapters.upstox import UpstoxAdapterConfig,UpstoxBrokerAdapter
from execution.engine import OrderRequest,OrderSide,OrderType
from execution.trading_execution import ExecutionAuthorization,ExecutionAuthorizationStatus
from trading.strategy.models import StrategyDirection
TS=pd.Timestamp("2026-09-25T10:00:00+05:30")
def order():
 a=ExecutionAuthorization(timestamp=TS,symbol="ITC",direction=StrategyDirection.LONG,status=ExecutionAuthorizationStatus.AUTHORIZED,reason="test",risk_version="risk-v1",approved_quantity=10,approved_notional=1500)
 return OrderRequest("SB-test","decision","ITC",OrderSide.BUY,10,OrderType.LIMIT,150,created_at=TS,authorization=a)
class Client:
 def place_order_v3(self,p): self.payload=p; return {"status":"success","data":{"order_ids":["OID-1"]}}
 def get_order(self,oid): return {"status":"success","data":{"order_id":oid,"quantity":10,"filled_quantity":10,"average_price":150,"status":"complete"}}
 def cancel_order(self,oid): return {"status":"success","data":{"order_id":oid}}
 def positions(self): return {"status":"success","data":{"net_positions":[{"trading_symbol":"ITC","quantity":10,"average_price":150}]}}
def test_config_is_sandbox_only():
 with pytest.raises(ValueError): UpstoxAdapterConfig(enabled=True,sandbox=False)
def test_disabled_by_default():
 with pytest.raises(RuntimeError): UpstoxBrokerAdapter(UpstoxAdapterConfig()).submit(order())
def test_payload_and_submit():
 c=Client(); a=UpstoxBrokerAdapter(UpstoxAdapterConfig(enabled=True,sandbox=True),c); s=a.submit(order()); assert s.broker_order_id=="OID-1"; assert c.payload["transaction_type"]=="BUY"
def test_get_cancel_and_positions():
 a=UpstoxBrokerAdapter(UpstoxAdapterConfig(enabled=True,sandbox=True),Client()); assert a.get_order("OID-1").status.value=="FILLED"; assert a.cancel("OID-1").status.value=="CANCELLED"; assert a.positions()[0].quantity==10
def test_invalid_place_response_fails_closed():
 class Bad(Client):
  def place_order_v3(self,p): return {"status":"success","data":{}}
 a=UpstoxBrokerAdapter(UpstoxAdapterConfig(enabled=True,sandbox=True),Bad())
 with pytest.raises(ValueError,match="order_ids"): a.submit(order())
