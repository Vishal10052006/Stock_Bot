from workers.base_worker import BaseWorker


class MathWorker(BaseWorker):

    def __init__(self):
        super().__init__(
            name="math",
            capabilities=["calculate", "math"],
            risk_level="low"
        )

    async def execute(self, task: str):
        return f"Solving math task: {task}"
    