from workers.base_worker import BaseWorker

class WritingWorker(BaseWorker):
    
    def __init__(self):
        super().__init__("WritingWorker")

    def execute(self, task: str):
        return f"[WritingWorker] Writing content for: {task}"