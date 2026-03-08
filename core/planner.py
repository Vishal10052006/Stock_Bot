class TaskPlanner:

    def create_plan(self, command: str):
        command = command.lower()

        plan = []

        if "blog" in command:

            plan = [
                {"step": 1, "intent": "research", "task": "research topic"},
                {"step": 2, "intent": "writing", "task": "creatwritingutline"},
                {"step": 3, "intent": "writing", "task": command},
                {"step": 4, "intent": "writing", "task": "optimize SEO"},
                {"step": 5, "intent": "writing", "task": "publish blog"}                
            ]

        # Research workflow
        elif "research" in command:

            plan = [
                {"step": 1, "intent": "research", "task": command},
                {"step": 2, "intent": "writing", "task": "summarize research"}
            ]

        else:

            plan = [
                {"step": 1, "intent": "writing", "task": command}
            ]

        return plan