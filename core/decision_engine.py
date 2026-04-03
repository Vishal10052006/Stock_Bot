from core import trust_manager
from core.confidence_calculator import calculate_confidence
from core.risk_calculator import calculate_risk
from core.decision_type import DecisionScore
from core.learning_engine import LearningEngine
from core.memory_manager import MemoryManager
from core.strategy_engine import StrategyEngine


class DecisionEngine:
    def __init__(self, memory_manager):
        self.memory_manager = MemoryManager()
        self.learning_engine = LearningEngine(self.memory_manager)
        self.strategy_engine = StrategyEngine()

    def select_worker(self, task, available_workers, trust_manager):

        import random

        # ⚡ Exploration
        if random.random() < 0.3:
            print("⚡ Exploring random worker")
            return random.choice(available_workers)

        scored = []

        for worker in available_workers:

            trust = trust_manager.get_trust(worker)

            # normal scoring
            score = self.calculate_advanced_score(worker, task, trust_manager)
            scored.append((worker, score))

        return max(scored, key=lambda x: x[1])[0]

    def make_decision(self, task_type, critic_score, goal, available_workers, trust_manager):

        # TRY STRATEGY FIRST
        strategy_output = self.strategy_engine.create_strategy(task_type)

        self.last_strategy = strategy_output

        if strategy_output:
            scored = []

            for worker in available_workers:
                trust = trust_manager.get_trust(worker)

                risk = self.estimate_risk(worker, task_type)
                time_cost = self.estimate_time(worker, task_type)
                skill_gain = self.estimate_skill_gain(worker, task_type)
                goal_value = self.estimate_goal_value(task_type)

                # 🔥 FINAL SCORE
                score = (
                    0.4 * trust +
                    0.2 * (1 - risk) +
                    0.2 * (1 - time_cost) +
                    0.1 * skill_gain +
                    0.1 * goal_value
                )

                scored.append((worker, score))

            # pick best worker
            worker_name = max(scored, key=lambda x: x[1])[0]

            print(f"🧠 Selected worker: {worker_name}")

        else:
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

        # ADD THIS BEFORE RETURN
        trust = trust_manager.get_trust(worker_name)
        risk = self.estimate_risk(worker_name, task_type)
        time_cost = self.estimate_time(worker_name, task_type)
        skill_gain = self.estimate_skill_gain(worker_name, task_type)
        goal_value = self.estimate_goal_value(task_type)

        return {
            "worker": worker_name,
            "decision": decision,
            "confidence": round(confidence, 2),
            "risk": risk,

            "reason": f"""
        Worker: {worker_name}
        Trust: {trust}
        Risk: {risk}
        Time: {time_cost}
        Skill Gain: {skill_gain}
        Goal Value: {goal_value}
        """
        }
    
    def explain(self, decision_data):
        return f"""
    Decision: {decision_data['decision']}
    Confidence: {decision_data['confidence']}
    Risk: {decision_data['risk']}
    Reason: Based on past performance and current score
    """
    # SCORING FUNCTION THAT COMBINES MULTIPLE DOMAINS
    def calculate_advanced_score(self, worker, task, trust_manager):

        trust = trust_manager.get_trust(worker)

        # Dynamic factors
        risk = self.estimate_risk(worker, task)
        time_cost = self.estimate_time(worker, task)
        skill_gain = self.estimate_skill_gain(worker, task)
        goal_value = self.estimate_goal_value(task)

        score = (
            trust * 0.2 +
            goal_value * 0.2 +
            skill_gain * 0.25 +
            (1 - time_cost) * 0.2 -
            risk * 0.15
        )
        memory = self.memory_manager.load_memory()
        penalty = self.adjust_for_past_failures(worker, memory)
        score += penalty

        return score
    
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
        if worker == "research_worker":
            return 0.4
        elif worker == "writing_worker":
            return 0.2
        return 0.3
    
    # Time estimation
    def estimate_time(self, worker, task):
        if worker == "research_worker":
            return 0.7
        elif worker == "writing_worker":
            return 0.5
        return 0.4
    
    # Skill gain
    def estimate_skill_gain(self, worker, task):
        if "blog" in task.lower():
            if worker == "writing_worker":
                return 0.9
            elif worker == "research_worker":
                return 0.7
        return 0.5
    
    # Goal importance
    def estimate_goal_value(self, task):
        if "blog" in task.lower():
            return 0.8
        return 0.5
    
    # MEMORY-BASED LEARNING
    def adjust_for_past_failures(self, worker, memory):
        failures = [
            m for m in memory
            if m.get("worker") == worker and m.get("result") == "FAILED"
        ]

        if len(failures) >= 2:
            return -0.2

        return 0
    


