from core.memory_manager import MemoryManager
from memory.session_memory import SessionMemory
from core.execution_engine import ExecutionEngine
from core.decision_engine import DecisionEngine
from core.goal_manager import GoalManager
from core.strategy_engine import StrategyEngine
from core.weight_manager import WeightManager
from core.reinforcement_engine import ReinforcementEngine
from core.decision_simulator import DecisionSimulator
from core.learning_engine import LearningEngine
from core.trust_manager import TrustManager

class CEO:
    # Constructor (__init__)
    def __init__(self):
        self.trust_manager = TrustManager()
        self.memory = SessionMemory()
        self.memory_manager = MemoryManager()
        self.execution_engine = ExecutionEngine(
            self.trust_manager,
            self.memory_manager
        )
        self.decision_engine = DecisionEngine(self.memory_manager)
        self.goal_manager = GoalManager()
        self.strategy_engine = StrategyEngine()
        self.decision_simulator = DecisionSimulator()
        self.learning_engine = LearningEngine(self.memory_manager)
        self.weight_manager = WeightManager()
        self.reinforcement_engine = ReinforcementEngine()
             
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

        # Only execute if allowed
        if decision["decision"] == "EXECUTE":
            results = await self.execution_engine.run(
                command,
                self.memory_manager,
                decision["worker"],
                self.trust_manager
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
        return self.decision_simulator.simulate(goal)