from workers.base_worker import BaseWorker
import asyncio

class ResearchWorker(BaseWorker):

    name = "research_worker"

    capabilities = ["research", "search"]

    def run(self, task):

        topic = task["input"]

        return f"Research result for {topic}"