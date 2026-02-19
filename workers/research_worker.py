from workers.base_worker import BaseWorker

class ResearchWorker(BaseWorker):
    def __init__(self):
        super().__init__("ResearchWorker")

    def execute(self, task: str):
        return f"[ResearchWorker] Researching topic: {task}"
