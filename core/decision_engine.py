from core.confidence_calculator import calculate_confidence
from core.risk_calculator import calculate_risk
from core.decision_type import DecisionScore
from core.learning_engine import LearningEngine
from core.memory_manager import MemoryManager


class DecisionEngine:
    def __init__(self, memory_manager):
        self.memory_manager = MemoryManager()
        self.learning_engine = LearningEngine(self.memory_manager)

    def make_decision(self, worker_name, task_type, critic_score, goal):
        
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
            "decision": decision,
            "confidence": round(confidence, 2),
            "risk": risk
        }