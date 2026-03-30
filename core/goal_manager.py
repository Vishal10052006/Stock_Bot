class GoalManager:
    def __init__(self):
        self.goals = []

    def add_goal(self, goal):
        self.goals.append(
            {
                "goal": goal,
                "status": "active",
                "progress": 0
            }
        )

    def get_active_goals(self):
        return [g for g in self.goal if g["status"] == "active"]