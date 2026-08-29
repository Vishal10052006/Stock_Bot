"""
Stock Bot — Task Planner

Phase 2 planning boundary.

Responsibilities:
    1. Convert a user command into an execution plan.
    2. Preserve deterministic step ordering.
    3. Assign an intent to each step.

The planner does NOT:
    - select workers,
    - execute workers,
    - evaluate worker reliability,
    - inspect execution memory,
    - modify the plan based on historical outcomes.
"""


class TaskPlanner:
    """Create deterministic execution plans from user commands."""

    def create_plan(self, command: str, memory=None):
        """
        Convert a user command into an ordered execution plan.

        Args:
            command: User task description.
            memory: Legacy parameter retained for API compatibility.
                It is intentionally ignored by the planner.

        Returns:
            List of ordered plan steps.
        """

        # Normalize only for intent detection. Preserve the user's
        # original command in the actual task where appropriate.
        normalized_command = command.lower()

        # Blog workflow.
        if "blog" in normalized_command:
            return [
                {
                    "step": 1,
                    "intent": "research",
                    "task": "research topic",
                },
                {
                    "step": 2,
                    "intent": "writing",
                    "task": "create outline",
                },
                {
                    "step": 3,
                    "intent": "writing",
                    "task": command,
                },
                {
                    "step": 4,
                    "intent": "writing",
                    "task": "optimizeSEO",
                },
                {
                    "step": 5,
                    "intent": "writing",
                    "task": "publish blog",
                },
            ]

        # Research workflow.
        if "research" in normalized_command:
            return [
                {
                    "step": 1,
                    "intent": "research",
                    "task": command,
                },
                {
                    "step": 2,
                    "intent": "writing",
                    "task": "summarize research",
                },
            ]

        # Default single-step workflow.
        return [
            {
                "step": 1,
                "intent": "writing",
                "task": command,
            }
        ]
