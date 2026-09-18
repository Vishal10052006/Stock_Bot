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
        # Core managers used by the legacy orchestration layer.
        self.trust_manager = TrustManager()
        self.memory_manager = MemoryManager()
        self.goal_manager = GoalManager()
        self.decision_simulator = DecisionSimulator()

        self.learning_engine = LearningEngine(self.memory_manager)
        self.reinforcement_engine = ReinforcementEngine()
        self.reliability_manager = ReliabilityManager()

        self.strategy_engine = StrategyEngine()
        self.weight_manager = WeightManager()

        self.execution_engine = ExecutionEngine()

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
            critic_score=None,
            goal="default",
            available_workers=available_workers,
            trust_manager=self.trust_manager
        )
        worker_name = decision.get("worker")

        # Only execute if allowed
        if decision["decision"] == "EXECUTE":
            results = await self.execution_engine.run(
                command,
                worker_name
            )

            # Trading reinforcement is intentionally disabled here.
            #
            # A worker/execution response is not a realized market
            # outcome. Trading learning may only update from an
            # objectively observed result such as realized P&L after
            # a completed position.

        else:
            return {
                "status": decision["decision"],
                "reason": decision
            }

        print("TRUST SCORES:", self.trust_manager.get_all_trust())
        return results

    def evaluate_result(self, result):
        """
        Convert real-world result into numeric score (0–1)
        """
        if result == "SUCCESS":
            return 1.0
        elif result == "PARTIAL":
            return 0.6
        elif result == "FAILED":
            return 0.0
        return 0.5

    def simulate_decision(self, goal):
        """Simulate a decision through the existing decision simulator."""
        return self.decision_simulator.simulate(goal)
