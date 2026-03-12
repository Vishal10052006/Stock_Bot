class WorkerRegistry:

    def __init__(self):
        self.workers = []

    def register(self, worker):

        self.workers.append(worker)

    def get_workers(self, task_type):

        candidates = []

        for worker in self.workers:

            if task_type in worker.capabilities:
                candidates.append(worker)

        return candidates