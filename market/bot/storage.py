"""MB-14 append-only JSONL state store."""
from pathlib import Path
import json
from dataclasses import asdict
class MarketStateStore:
    def __init__(self,path="data/market_bot/states.jsonl"): self.path=Path(path)
    def append(self,state,provenance=None):
        self.path.parent.mkdir(parents=True,exist_ok=True); r=asdict(state)
        if provenance is not None: r["provenance_record"]=provenance.to_dict()
        with self.path.open("a",encoding="utf-8") as f: f.write(json.dumps(r,default=str,sort_keys=True)+"\n")
    def read(self):
        if not self.path.exists(): return []
        with self.path.open(encoding="utf-8") as f: return [json.loads(x) for x in f if x.strip()]
