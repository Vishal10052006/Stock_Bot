import asyncio
from workers.base_worker import BaseWorker

class WritingWorker(BaseWorker):
    
    def __init__(self):
        super().__init__(
            name = "writing",
            capabilities=["write", "blog", "article"],
            risk_level="low"
        )

    async def execute(self, task: str):
        return f"Writing content for: {task}"