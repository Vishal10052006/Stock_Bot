from unittest import result

from core import trust_manager
from core.confidence_calculator import calculate_confidence
from core.risk_calculator import calculate_risk
from core.decision_type import DecisionScore
from core.learning_engine import LearningEngine
from core.memory_manager import MemoryManager
from core.strategy_engine import StrategyEngine
from core.weight_manager import WeightManager
from core.reinforcement_engine import ReinforcementEngine


class DecisionEngine:
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        self.weight_manager = WeightManager()
        self.reinforcement_engine = ReinforcementEngine()
        self.learning_engine = LearningEngine(self.memory_manager)
        self.strategy_engine = StrategyEngine()

# 1. Main decision function that combines all factors
    def calculate_advanced_score(self, worker, task, trust_manager):

        trust = trust_manager.get_trust(worker)

        risk = self.estimate_risk(worker, task)
        time_cost = self.estimate_time(worker, task)
        skill_gain = self.estimate_skill_gain(worker, task)
        goal_value = self.estimate_goal_value(task)

        # unified factors
        factors = {
            "trust": trust,
            "risk": (1 - risk),
            "time": (1 - time_cost),
            "skill": skill_gain,
            "goal": goal_value
        }

        # dynamic weights (PHASE 6 CORE)
        weights = self.weight_manager.get_weights()

        score = (
            weights["trust"] * factors["trust"] +
            weights["risk"] * factors["risk"] +
            weights["time"] * factors["time"] +
            weights["skill"] * factors["skill"] +
            weights["goal"] * factors["goal"]
        )

        # memory penalty (optional but ok)
        memory = self.memory_manager.load_memory()
        score += self.adjust_for_past_failures(worker, memory)

        return score, factors
    
# 2. Worker selection based on scores
    def select_worker(self, task, available_workers, trust_manager):

        scored = []

        for worker in available_workers:
            score, _ = self.calculate_advanced_score(worker, task, trust_manager)
            scored.append((worker, score))
            print(f"{worker} score: {score}")

        return max(scored, key=lambda x: x[1])[0]
    
# 3. Main function to execute decision and learn from result
    def make_decision(self, task_type, critic_score, goal, available_workers, trust_manager):

        import random

        # Dynamic exploration rate
        experience = self.learning_engine.get_experience()
        exploration_rate = max(0.1, 0.4 - experience * 0.01)

        if random.random() < exploration_rate:
            worker_name = random.choice(available_workers)
            print("Exploring worker:", worker_name)

            return {
                "worker": worker_name,
                "decision": "EXECUTE",
                "confidence": 0.5,
                "risk": "medium",
                "factors": {},
                "reason": "Exploration mode"
            }

        strategy_output = self.strategy_engine.create_strategy(task_type)
        self.last_strategy = strategy_output

        scored = []

        # 🔥 USE SAME FUNCTION (NO DUPLICATE LOGIC)
        for worker in available_workers:
            score, factors = self.calculate_advanced_score(worker, task_type, trust_manager)
            scored.append((worker, score, factors))

        # pick best worker
        worker_name, best_score, best_factors = max(scored, key=lambda x: x[1])

        print(f"Selected worker: {worker_name}")

        # confidence
        confidence = critic_score / 10

        # adjust using memory
        memory = self.memory_manager.load_memory()
        failures = [
            m for m in memory
            if m.get("worker") == worker_name and m.get("result") == "FAILED"
        ]

        if len(failures) >= 3:
            confidence *= 0.7

        # risk label
        if confidence > 0.7:
            decision = "EXECUTE"
            risk_label = "low"
        elif confidence > 0.4:
            decision = "ASK_USER"
            risk_label = "medium"
        else:
            decision = "BLOCK"
            risk_label = "high"

        result = {
            "worker": worker_name,
            "decision": decision,
            "confidence": round(confidence, 2),
            "risk": risk_label,
            "factors": best_factors,
            "reason": f"Worker: {worker_name} | Score: {round(best_score, 3)} | Confidence: {confidence}"
                }

        import random

        predicted = result["confidence"]
        actual = random.uniform(0.4, 1.0)

        reward = self.reinforcement_engine.calculate_reward(predicted, actual)

        weights = self.weight_manager.get_weights()

        feedback = self.reinforcement_engine.generate_feedback(
            best_factors,
            reward
        )

        self.weight_manager.update_weights(feedback)

        print("🧠 UPDATED WEIGHTS:", self.weight_manager.get_weights())

        # ✅ FINAL RETURN
        return result

# 4. Function to execute task and learn from result
    def explain(self, decision_data):
        return f"""
    Decision: {decision_data['decision']}
    Confidence: {decision_data['confidence']}
    Risk: {decision_data['risk']}
    Reason: Based on past performance and current score
    """
# 5. FACTOR ESTIMATION FUNCTIONS (SIMPLIFIED FOR DEMO)        
    def estimate_goal_value(self, task):
        return 0.9           # profit importance
    
    def estimate_risk(self, worker, task):
        if "technical" in worker:
            return 0.3
        elif "sentiment" in worker:
            return 0.5
        return 0.2
    
    def estimate_skill_gain(self, worker, task):
        return 0.7
    
    def estimate_time(self, worker, task):
        return 0.4
    
    # INTELLIGENCE FUNCTIONS
    def estimate_risk(self, worker, task):
        if worker == "technical_worker":
            return 0.3
        elif worker == "sentiment_worker":
            return 0.6
        elif worker == "strategy_worker":
            return 0.4
        return 0.5


    def estimate_time(self, worker, task):
        if worker == "technical_worker":
            return 0.6   # slower
        elif worker == "sentiment_worker":
            return 0.3   # fast
        elif worker == "strategy_worker":
            return 0.5
        return 0.4


    def estimate_skill_gain(self, worker, task):
        if worker == "technical_worker":
            return 0.8
        elif worker == "sentiment_worker":
            return 0.6
        elif worker == "strategy_worker":
            return 0.9
        return 0.5


    def estimate_goal_value(self, task):
        if "stock" in task.lower():
            return 0.9
        return 0.6
    
    # MEMORY-BASED LEARNING
    def adjust_for_past_failures(self, worker, memory):
        failures = [
            m for m in memory
            if m.get("worker") == worker and m.get("result") == "FAILED"
        ]

        if len(failures) >= 2:
            return -0.2

        return 0
    


