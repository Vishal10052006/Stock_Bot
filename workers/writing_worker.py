import asyncio
from workers.base_worker import BaseWorker

class WritingWorker(BaseWorker):
    
    def __init__(self):
        super().__init__("WritingWorker")

    async def execute(self, task: str):
        await asyncio.sleep(1)  # simulate work
        return f"[WritingWorker] Writing content for: {task}"
