"""MB-21 fail-closed semantics."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class FailurePolicy:
    missing_data_state:str="UNAVAILABLE"; fail_closed:bool=True; allow_partial:bool=True
def unavailable_reason(error): return {"status":"UNAVAILABLE","reason":type(error).__name__+":"+str(error),"trade_authority":False}
