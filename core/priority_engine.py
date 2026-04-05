# priority_engine

class PriorityEngine:

    def assign_priority(self, tasks):
        for task in tasks:
            name = task["task"].lower()

            if "core" in name or "architecture" in name:
                task["priority"] = "high"

            elif "test" in name:
                task["priority"] = "medium"

            else:
                task["priority"] = "low"

        return tasks