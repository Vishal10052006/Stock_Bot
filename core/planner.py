class TaskPlanner:

    def create_plan(self, command: str, memory=None):
        command = command.lower()

        plan = []

        if "blog" in command:

            plan = [
                {"step": 1, "intent": "research", "task": "research topic"},
                {"step": 2, "intent": "writing", "task": "create outline"},
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

        # MEMORY-BASED IMPROVEMENT
        bad_tasks = []
        preferred_tasks = []

        if memory:
            for m in memory:

                # Track failures
                if m.get("type") == "mistake":
                    bad_tasks.append(m.get("task"))

                # Track success
                if m.get("result") == "SUCCESS":
                    preferred_tasks.append(m.get("task"))

        # Remove bad tasks
        filtered_plan = []
        for step in plan:
            if step["task"] in bad_tasks:
                continue
            filtered_plan.append(step)

        # Prioritize good tasks
        filtered_plan = sorted(
            filtered_plan,
            key=lambda x: x["task"] in preferred_tasks,
            reverse=True
        )

        return filtered_plan