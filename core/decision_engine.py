from core.confidence_calculator import calculate_confidence
from core.risk_calculator import calculate_risk
from core.decision_type import DecisionScore


def make_decision(worker_name, task_type, critic_score):

    confidence = calculate_confidence(worker_name, critic_score)

    risk = calculate_risk(task_type)

    final_score = confidence - risk

    if final_score >= 0.4:
        decision = "AUTO_EXECUTE"

    elif final_score >= 0:
        decision = "ASK_USER"

    else:
        decision = "BLOCK"

    return DecisionScore(
        confidence=confidence,
        risk=risk,
        final_score=final_score,
        decision=decision
    )