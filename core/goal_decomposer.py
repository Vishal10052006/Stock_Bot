# core/goal_decomposer.py

class GoalDecomposer:

    def decompose(self, goal):
        goal = goal.lower()

        if "ai" in goal:
            return [
                {"task": "Design system architecture", "type": "technical"},
                {"task": "Build core AI logic", "type": "technical"},
                {"task": "Create user interface", "type": "product"},
                {"task": "Test and debug system", "type": "quality"},
                {"task": "Deploy application", "type": "deployment"}
            ]

        elif "blog" in goal:
            return [
                {"task": "Research content topics", "type": "research"},
                {"task": "Write articles", "type": "content"},
                {"task": "Optimize SEO", "type": "growth"},
                {"task": "Publish consistently", "type": "execution"}
            ]

        else:
            return [
                {"task": f"Plan {goal}", "type": "general"},
                {"task": f"Execute {goal}", "type": "general"},
                {"task": f"Review {goal}", "type": "general"}
            ]