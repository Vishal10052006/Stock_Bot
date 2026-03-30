# strategy_engine

from core.timeline_builder import TimelineBuilder

class StrategyEngine:
    def __init__(self):
        self.timeline_builder = TimelineBuilder()

    def create_strategy(self, goal):
        timeline = self.timeline_builder.build_timeline(goal)

        strategy = {
            "goal": goal,
            "timeline": timeline,
            "strategy_summary": f"Long-term plan created for {goal}"
        }

        return strategy