from core.memory_manager import MemoryManager
from memory.session_memory import SessionMemory
from execution_engine import ExecutionEngine

from core.goal_manager import GoalManager
from core.strategy_engine import StrategyEngine

class CEO:
    # Constructor (__init__)
    def __init__(self):

        self.memory = SessionMemory()
        self.memory_manager = MemoryManager()
        self.execution_engine = ExecutionEngine()

        self.goal_manager = GoalManager()
        self.strategy_engine = StrategyEngine()

    def add_goal(self, goal):
        self.goal_manager.add_goal(goal)

    def plan_stratgies(self):
        goals = self.goal_manager.get_active_goals()
        strategies = []

        for g in goals:
            strategy = self.strategy_engine.create_strategy(g["goal"])
            strategies.append(strategy)

        return strategies

    async def act(self, command):
        return await self.execution_engine.run(command, self.memory_manager)