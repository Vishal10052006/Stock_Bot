class WorkerRegistry:
    def __init__(self):
        self.workers = {}

    def register(self, worker):
        self.workers[worker.name] = worker

    def all_workers(self):
        return list(self.workers.keys())

    def get_worker(self, worker_name):
        worker = self.workers.get(worker_name)

        if not worker:
            raise ValueError(f"Worker '{worker_name}' not found")

        return worker