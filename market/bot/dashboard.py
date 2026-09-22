"""MB-15 presentation-neutral dashboard payload."""
from dataclasses import asdict
def build_dashboard_payload(state,health=None):
    p={"market_state":asdict(state)}
    if health is not None: p["health"]=asdict(health)
    return p
