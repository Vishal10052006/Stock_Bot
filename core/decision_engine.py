from core.confidence_calculator import calculate_confidence
from core.risk_calculator import calculate_risk
from core.decision_type import DecisionScore
from core.learning_engine import LearningEngine
from core.memory_manager import MemoryManager


class DecisionEngine:
    def __init__(self, memory_manager):
        self.memory_manager = MemoryManager()
        self.learning_engine = LearningEngine(self.memory_manager)

    def select_worker(self, task, available_workers, trust_manager):

        import random

        # 🔥 STEP 1 — EXPLORATION (ADD HERE)
        if random.random() < 0.2:
            print("⚡ Exploring random worker")
            return random.choice(available_workers)

        # 🔥 STEP 2 — NORMAL SCORING
        scored = []

        for worker in available_workers:
            score = self.calculate_multi_domain_score(
                worker,
                task,
                trust_manager
            )
            scored.append((worker, score))

        return max(scored, key=lambda x: x[1])[0]

    def make_decision(self, task_type, critic_score, goal, available_workers, trust_manager):
        
        worker_name = self.select_worker(task_type, available_workers, trust_manager)
        
        # 1. Base confidence from critic
        confidence = critic_score / 10  # normalize (0–1)

        # 2. Adjust using past failures (learning influence)
        memory = self.memory_manager.load_memory()

        failures = [
            m for m in memory
            if m.get("worker") == worker_name and m.get("result") == "FAILED"
        ]

        if len(failures) >= 3:
            confidence *= 0.7   # reduce trust

        # 3. Risk calculation
        if confidence > 0.7:
            decision = "EXECUTE"
            risk = "low"
        elif confidence > 0.4:
            decision = "ASK_USER"
            risk = "medium"
        else:
            decision = "BLOCK"
            risk = "high"

        return {
            "worker": worker_name,
            "decision": decision,
            "confidence": round(confidence, 2),
            "risk": risk,
            "reason": f"Selected based on trust + goal + skill vs risk/time"
        }
    
    def explain(self, decision_data):
        return f"""
    Decision: {decision_data['decision']}
    Confidence: {decision_data['confidence']}
    Risk: {decision_data['risk']}
    Reason: Based on past performance and current score
    """

    def calculate_multi_domain_score(self, worker, task, trust_manager):

        trust = trust_manager.get_trust(worker)

        # Example dynamic behavior
        if worker == "writing_worker":
            skill_gain = 0.9
            time_cost = 0.6
        elif worker == "research_worker":
            skill_gain = 0.7
            time_cost = 0.4
        else:
            skill_gain = 0.5
            time_cost = 0.3

        risk = 0.3
        goal_value = 0.8

        score = (
            trust * 0.2 +
            goal_value * 0.2 +
            skill_gain * 0.3 +
            (1 - time_cost) * 0.2 -
            risk * 0.1
        )

        return score