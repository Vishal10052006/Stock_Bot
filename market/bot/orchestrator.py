"""MB-13 Market Bot orchestration."""
import pandas as pd
from .engines import MarketTrendEngine,MarketRangeEngine,MarketVolatilityEngine,MarketBreadthEngine,SectorIntelligenceEngine,SectorRotationEngine,CorrelationDependencyEngine,LiquidityFlowEngine,MarketStrengthEngine
from .transitions import fuse_market_state
from .validation import validate_market_input,validate_state
from .provenance import build_provenance
class MarketBotOrchestrator:
    version="market-bot-v1"
    def run(self,data,*,benchmark,as_of=None,data_version="unknown",feature_version="market-bot-v1"):
        validate_market_input(data); f=data.copy(); f["timestamp"]=pd.to_datetime(f.timestamp,utc=True)
        trend=MarketTrendEngine().calculate(f); rng=MarketRangeEngine().calculate(f); vol=MarketVolatilityEngine().calculate(f)
        breadth=MarketBreadthEngine().calculate(f) if "symbol" in f else pd.DataFrame(); sectors=SectorIntelligenceEngine().calculate(f) if "sector" in f else pd.DataFrame(); rotation=SectorRotationEngine().calculate(sectors) if not sectors.empty else sectors; corr=CorrelationDependencyEngine().calculate(f) if "symbol" in f else pd.DataFrame(); liq=LiquidityFlowEngine().calculate(f) if "volume" in f else pd.DataFrame(); strength=MarketStrengthEngine().calculate(trend)
        ts=pd.Timestamp(as_of if as_of is not None else f.timestamp.max()); row=trend.loc[trend.timestamp<=ts].iloc[-1]
        def latest(df,col):
            if df.empty or col not in df: return None
            z=df.loc[pd.to_datetime(df.timestamp,utc=True)<=ts,col].dropna(); return None if z.empty else z.iloc[-1]
        parts={"trend_state":row.get("trend_state"),"trend_strength":row.get("trend_strength"),"range_state":row.get("range_state"),"volatility_state":latest(vol,"volatility_state"),"breadth_state":latest(breadth,"breadth_state"),"sector_state":latest(sectors,"sector_state"),"rotation_state":latest(rotation,"rotation_state"),"correlation_state":latest(corr,"correlation_state"),"liquidity_state":latest(liq,"liquidity_state"),"strength_state":latest(strength,"strength_state")}
        q=sum(v not in (None,"UNAVAILABLE") for v in parts.values())/len(parts); state=fuse_market_state(parts,timestamp=ts.to_pydatetime(),benchmark=benchmark,quality=q,version=self.version); validate_state(state)
        prov=build_provenance(bot_version=self.version,data_version=data_version,feature_version=feature_version,benchmark=benchmark,as_of=ts.to_pydatetime(),sources=("market_data","deterministic_engines"))
        return state,{"trend":trend,"range":rng,"volatility":vol,"breadth":breadth,"sector":sectors,"rotation":rotation,"correlation":corr,"liquidity":liq,"strength":strength,"provenance":prov}
