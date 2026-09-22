"""MB-14 provenance."""
from dataclasses import dataclass,asdict
from datetime import datetime
@dataclass(frozen=True,slots=True)
class ProvenanceRecord:
    bot_version:str; data_version:str; feature_version:str; benchmark:str; as_of:datetime; sources:tuple[str,...]; parameters:dict
    def to_dict(self):
        d=asdict(self); d["as_of"]=self.as_of.isoformat(); return d
def build_provenance(*,bot_version,data_version,feature_version,benchmark,as_of,sources=(),parameters=None):
    if as_of.tzinfo is None: raise ValueError("as_of must be timezone-aware")
    return ProvenanceRecord(bot_version,data_version,feature_version,benchmark.strip().upper(),as_of,tuple(sorted(set(sources))),dict(parameters or {}))
