from workers.base_worker import BaseWorker
import asyncio

class ResearchWorker(BaseWorker):
    def __init__(self):
        super().__init__("ResearchWorker")

    async def execute(self, task: str):
        await asyncio.sleep(1)  # simulate work
        return f"Writing content for: {task}"