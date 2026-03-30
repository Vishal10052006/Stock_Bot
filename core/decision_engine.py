from core.confidence_calculator import calculate_confidence
from core.risk_calculator import calculate_risk
from core.decision_type import DecisionScore
from core.learning_engine import LearningEngine


class DecisionEngine:
    def __init__(self):
        self.learning_engine = LearningEngine()

    def make_decision(self, worker_name, task_type, critic_score, goal="unknown"):
        
        # Step 1: confidence
        confidence = calculate_confidence(worker_name, critic_score)

        # Step 2: risk
        risk = calculate_risk(task_type)

        # Step 3: score
        final_score = confidence - risk

        # Step 4: decision
        if final_score >= 0.4:
            decision = "AUTO_EXECUTE"
        elif final_score >= 0:
            decision = "ASK_USER"
        else:
            decision = "BLOCK"

        # Step 5: simulate outcome (temporary)
        actual_outcome = final_score   # placeholder

        # ✅ STEP 6 — RECORD DECISION
        self.learning_engine.record_outcome(
            goal,
            decision,
            final_score,
            actual_outcome
        )

        return DecisionScore(
            confidence=confidence,
            risk=risk,
            final_score=final_score,
            decision=decision
        )