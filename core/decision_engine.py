from core.confidence_calculator import calculate_confidence
from core.risk_calculator import calculate_risk
from core.decision_type import DecisionScore
from core.learning_engine import LearningEngine
from core.memory_manager import MemoryManager


class DecisionEngine:
    def __init__(self, memory_manager):
        self.memory_manager = MemoryManager()
        self.learning_engine = LearningEngine(self.memory_manager)

    def select_worker(self, task_type, available_workers, trust_manager):
        scored = []

        for worker in available_workers:
            # Base score from your system (you can improve later)
            base_score = 0.5  

            trust = trust_manager.get_trust(worker)

            final_score = base_score * 0.7 + trust * 0.3
            scored.append((worker, final_score))

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
            "worker": worker_name,   # 🔥 ADD THIS LINE
            "decision": decision,
            "confidence": round(confidence, 2),
            "risk": risk,
        }
    
    def explain(self, decision_data):
        return f"""
    Decision: {decision_data['decision']}
    Confidence: {decision_data['confidence']}
    Risk: {decision_data['risk']}
    Reason: Based on past performance and current score
    """