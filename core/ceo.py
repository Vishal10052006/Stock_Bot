from memory.memory_manager import MemoryManager
from memory.session_memory import SessionMemory

from execution.execution_engine import ExecutionEngine
from core.decision_engine import DecisionEngine
from core.goal_manager import GoalManager

from intelligence.strategy_engine import StrategyEngine
from intelligence.weight_manager import WeightManager
from intelligence.decision_simulator import DecisionSimulator

from learning.learning_engine import LearningEngine
from learning.reinforcement_engine import ReinforcementEngine
from learning.trust_manager import TrustManager
from learning.reliability_manager import ReliabilityManager

class CEO:
    # Constructor (__init__)
    def __init__(self):
                # Goal management for planning workflows.
        self.goal_manager = GoalManager()

        # Decision simulation for evaluating alternative approaches.
        self.decision_simulator = DecisionSimulator()
        self.trust_manager = TrustManager()
        self.memory_manager = MemoryManager()

        self.learning_engine = LearningEngine(self.memory_manager)
        self.reinforcement_engine = ReinforcementEngine()
        self.reliability_manager = ReliabilityManager()

        self.strategy_engine = StrategyEngine()
        
        self.weight_manager = WeightManager()
        self.reinforcement_engine = ReinforcementEngine()

        self.execution_engine = ExecutionEngine(
            self.trust_manager,
            self.memory_manager,
            self.learning_engine,
            self.reinforcement_engine,
            self.reliability_manager
        )

        self.decision_engine = DecisionEngine(
            self.memory_manager,
            self.trust_manager,
            self.learning_engine,
            self.strategy_engine,
            self.weight_manager,
            self.reinforcement_engine
        )
             
    def add_goal(self, goal):
        self.goal_manager.add_goal(goal)

    def plan_strategies(self):
        goals = self.goal_manager.get_active_goals()
        strategies = []

        for g in goals:
            strategy = self.strategy_engine.create_strategy(g["goal"])
            strategies.append(strategy)

        return strategies

    async def act(self, command):
        available_workers = [
            "technical_worker",
            "sentiment_worker",
            "strategy_worker"
        ]

        decision = self.decision_engine.make_decision(
            task_type=command,
            critic_score=8,  # (temporary, later from critic system)
            goal="default",
            available_workers=available_workers,
            trust_manager=self.trust_manager
        )
        worker_name = decision.get("worker", "strategy_worker")

        # Only execute if allowed
        if decision["decision"] == "EXECUTE":
            results = await self.execution_engine.run(
                command,
                worker_name
            )

            # REINFORCEMENT LEARNING BLOCK

            # 1. predicted
            predicted = decision["confidence"]

            # 2. actual (convert result → score)
            actual = self.evaluate_result(results)

            # 3. reward
            reward = self.reinforcement_engine.calculate_reward(predicted, actual)

            # 4. feedback
            feedback = self.reinforcement_engine.generate_feedback(
                decision["factors"],
                reward
            )

            # 5. update weights
            self.weight_manager.update_weights(feedback)

            # DEBUG
            print("🧠 UPDATED WEIGHTS:", self.weight_manager.get_weights())

        else:
            return {
                "status": decision["decision"],
                "reason": decision
            }

        print("TRUST SCORES:", self.trust_manager.get_all_trust())
        return results
    
    def evaluate_result(self, result):
        """
        Convert a worker execution result into a numeric score [0, 1].

        Supports the Phase 1 dictionary contract and legacy string
        results for backward compatibility.
        """

        if isinstance(result, dict):
            if result.get("success") is True:
                return float(result.get("confidence", 1.0))

            if result.get("success") is False:
                return 0.0

        if result == "SUCCESS":
            return 1.0

        if result == "PARTIAL":
            return 0.6

        if result == "FAILED":
            return 0.0

        return 0.5

    def simulate_decision(self, goal):
        return self.decision_simulator.simulate(goal)