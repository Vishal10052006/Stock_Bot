from dataclasses import dataclass

@dataclass
class DecisionScore:
    confidence: float
    risk: float
    final_score: float
    decision: str