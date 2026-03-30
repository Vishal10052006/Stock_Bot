# core/timeline_builder.py

class TimelineBuilder:
    def build_timeline(self, goal):
        return {
            "goal": goal,
            "monthly_plan": [
                f"Month 1: Research & Setup for {goal}",
                f"Month 2: Execution phase of {goal}",
                f"Month 3: Optimization of {goal}"
            ],
            "weekly_plan": [
                f"Week 1: Start {goal}",
                f"Week 2: Improve {goal}",
                f"Week 3: Scale {goal}"
            ],
            "milestones": [
                f"Initial version of {goal}",
                f"Working system of {goal}",
                f"Optimized system of {goal}"
            ]
        }