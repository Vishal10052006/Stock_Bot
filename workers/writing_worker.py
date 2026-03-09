from workers.base_worker import BaseWorker
import asyncio

class WritingWorker(BaseWorker):

    name = "writing_worker"

    capabilities = ["write", "blog"]

    def run(self, task):

        topic = task["input"]

        return f"Blog about {topic}"