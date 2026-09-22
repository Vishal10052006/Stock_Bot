"""MB-17 evaluation and MB-23 production gate."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class EvaluationReport:
    sample_count:int; available_rate:float; causal_checks_passed:bool; leakage_checks_passed:bool; integration_checks_passed:bool; production_ready:bool; notes:tuple[str,...]
def evaluate(states,*,causal_checks_passed=True,leakage_checks_passed=True,integration_checks_passed=True):
    s=list(states); n=len(s); rate=sum(x.availability!="UNAVAILABLE" for x in s)/n if n else 0
    ready=bool(n and rate>=.95 and causal_checks_passed and leakage_checks_passed and integration_checks_passed)
    return EvaluationReport(n,rate,causal_checks_passed,leakage_checks_passed,integration_checks_passed,ready,() if ready else ("production gate remains closed until evidence passes",))
