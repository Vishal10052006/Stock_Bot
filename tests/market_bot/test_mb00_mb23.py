import pandas as pd
from market.bot.contracts import MarketState
from market.bot.engines import MarketTrendEngine,MarketVolatilityEngine,MarketRangeEngine
from market.bot.orchestrator import MarketBotOrchestrator
from market.bot.evaluation import evaluate
from market.bot.integration import assert_no_trade_authority
from market.bot.versioning import assert_compatible
def sample_market(n=120,symbols=("AAA","BBB","CCC","DDD")):
    rows=[]
    for j,s in enumerate(symbols):
        for i,t in enumerate(pd.date_range("2026-01-01",periods=n,freq="D",tz="UTC")):
            c=100+j*5+i*.15+(i%7)*.02
            rows.append({"timestamp":t,"symbol":s,"close":c,"high":c+1,"low":c-1,"volume":100000+j*10000,"sector":"S"+str(j%2)})
    return pd.DataFrame(rows)
def test_trend_warmup_and_causality():
    x=sample_market().query("symbol=='AAA'").copy(); a=MarketTrendEngine().calculate(x); b=MarketTrendEngine().calculate(pd.concat([x,x.iloc[-1:].assign(timestamp=x.timestamp.iloc[-1]+pd.Timedelta(days=1),close=9999)],ignore_index=True))
    assert a.trend_state.iloc[0]=="UNAVAILABLE"; assert a.trend_state.iloc[-1]==b.trend_state.iloc[-2]
def test_range_and_volatility():
    x=sample_market().query("symbol=='AAA'").copy(); assert "range_state" in MarketRangeEngine().calculate(x); assert "volatility_state" in MarketVolatilityEngine().calculate(x)
def test_orchestrator():
    s,d=MarketBotOrchestrator().run(sample_market(),benchmark="NIFTY50"); assert s.benchmark=="NIFTY50"; assert_no_trade_authority(s)
def test_contract_gate():
    s=MarketState(pd.Timestamp("2026-01-01",tz="UTC").to_pydatetime(),"NIFTY50",quality=.5); assert_compatible(s.version); assert evaluate([s]).sample_count==1
def test_future_row_does_not_change_history():
    x=sample_market().query("symbol=='AAA'").copy(); a=MarketVolatilityEngine().calculate(x); y=pd.concat([x,x.iloc[-1:].assign(timestamp=x.timestamp.iloc[-1]+pd.Timedelta(days=1),close=5000)],ignore_index=True); b=MarketVolatilityEngine().calculate(y)
    pd.testing.assert_frame_equal(a[["volatility_realized","volatility_atr_normalized","volatility_state"]].iloc[:-1].reset_index(drop=True),b[["volatility_realized","volatility_atr_normalized","volatility_state"]].iloc[:-2].reset_index(drop=True))
