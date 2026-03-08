from workers.base_worker import BaseWorker
import asyncio

class WritingWorker(BaseWorker):

    def __init__(self):
        super().__init__(
            name="writing",
            capabilities=["write", "blog", "article"],
            risk_level="low"
        )

    async def execute(self, task: str):
        await asyncio.sleep(1)
        return f"Writing content for: {task}"