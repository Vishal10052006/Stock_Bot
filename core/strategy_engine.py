# strategy_engine

from core.goal_decomposer import GoalDecomposer
from core.dependency_engine import DependencyEngine
from core.priority_engine import PriorityEngine
from workers.strategy_worker import StrategyWorker

class StrategyEngine:
    def __init__(self):
        self.decomposer = GoalDecomposer()
        self.dependency_engine = DependencyEngine()
        self.priority_engine = PriorityEngine()
        self.memory_strategy = StrategyWorker()

    def create_strategy(self, goal):
        tasks = self.decomposer.decompose(goal)

        tasks = self.dependency_engine.assign_dependencies(tasks)
        tasks = self.priority_engine.assign_priority(tasks)

        strategy = {
            "goal": goal,
            "tasks": tasks,
            "summary": f"Strategic plan created for {goal}"
        }

        return strategy
    
    def execute(self, task):
        return self.memory_strategy.execute(task)
    

    ''' StrategyEngine
 ├── create_strategy()  → planning
 └── execute()          → learning from memory '''