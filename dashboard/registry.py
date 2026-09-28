from __future__ import annotations
PRIMARY_AGENTS=(
("AG-01","RESEARCH_BOT","Research and point-in-time context","Market / historical evidence","ResearchContext",False),
("AG-02","ANALYSIS_BOT","Feature/context interpretation","ResearchContext + approved features","AnalysisContext",False),
("AG-03","MARKET_BOT","Market/regime context","Validated market/candle state","MarketContext / regime",False),
("AG-04","PREDICTION_BOT","Model inference","Decision-time feature vector","Prediction + lineage",False),
("AG-05","STRATEGY_BOT","Trade candidate generation","Prediction + context","TradeCandidate",False),
("AG-06","RISK_BOT","Risk authorization","TradeCandidate + account state","Risk decision / authorization",False),
("AG-07","EXECUTION_BOT","Paper execution boundary","Risk-authorized order","Paper order / fill state",True),
)
PIPELINE=(("01","RESEARCH","AG-01"),("02","ANALYSIS","AG-02"),("03","MARKET","AG-03"),("04","PREDICTION","AG-04"),("05","STRATEGY","AG-05"),("06","RISK","AG-06"),("07","EXECUTION","AG-07"))
SOURCE_TO_AGENT={"research":"AG-01","research_bot":"AG-01","analysis":"AG-02","analysis_bot":"AG-02","market":"AG-03","market_bot":"AG-03","prediction":"AG-04","model":"AG-04","strategy":"AG-05","risk":"AG-06","execution":"AG-07","paper_execution":"AG-07"}
def agent_records():
    return [{"agent_id":a[0],"name":a[1],"role":a[2],"input_contract":a[3],"output_contract":a[4],"locked":a[5],"order":i+1} for i,a in enumerate(PRIMARY_AGENTS)]
