from core.memory_manager import MemoryManager
from memory.session_memory import SessionMemory
from core.execution_engine import ExecutionEngine
from core.decision_engine import DecisionEngine
from core.goal_manager import GoalManager
from core.strategy_engine import StrategyEngine

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

        # 👇 Only execute if allowed
        if decision["decision"] == "EXECUTE":
            results = await self.execution_engine.run(
                command,
                self.memory_manager,
                decision["worker"],
                self.trust_manager
            )
        else:
            return {
                "status": decision["decision"],
                "reason": decision
            }

        print("TRUST SCORES:", self.trust_manager.get_all_trust())
        return results
    
    def simulate_decision(self, goal):
        return self.decision_simulator.simulate(goal)