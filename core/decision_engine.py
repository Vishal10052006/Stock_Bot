from unittest import result

from learning.trust_manager import TrustManager
from core.decision_type import DecisionScore
from intelligence.weight_manager import WeightManager

class DecisionEngine:
    def __init__(self, memory_manager, trust_manager, learning_engine, strategy_engine, weight_manager, reinforcement_engine):
        self.memory_manager = memory_manager
        self.trust_manager = trust_manager
        self.learning_engine = learning_engine
        self.strategy_engine = strategy_engine
        self.weight_manager = weight_manager
        self.reinforcement_engine = reinforcement_engine

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

        if not available_workers:
            return {
                "worker": None,
                "decision": "BLOCK",
                "confidence": 0.0,
                "risk": "high",
                "factors": {},
                "reason": "No workers are available."
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

        # ---------------------------------------------------------
        # SAFETY BOUNDARY
        # ---------------------------------------------------------
        #
        # The legacy worker/critic score is NOT a trading confidence
        # measure. It must never authorize a financial transaction.
        #
        # Until a validated trading strategy and risk decision are
        # supplied by the production trading pipeline, this legacy
        # coordinator fails closed.
        #
        # Real trading confidence must eventually come from the
        # strategy/model pipeline using causally valid market features,
        # followed by independent risk validation.
        # ---------------------------------------------------------

        result = {
            "worker": worker_name,
            "decision": "BLOCK",
            "confidence": None,
            "risk": "high",
            "factors": best_factors,
            "reason": (
                "Legacy DecisionEngine cannot authorize trading. "
                "A validated strategy and risk decision are required."
            ),
        }

        # Learning is deliberately NOT performed here.
        #
        # A decision prediction is not a realized trading outcome.
        # Reinforcement updates require an objectively observed market
        # result such as realized P&L after a completed trade.

        # FINAL RETURN
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
    


