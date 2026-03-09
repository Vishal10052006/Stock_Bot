class WorkerRegistry:

    def __init__(self):
        self.workers = {}

    def register(self, worker):

        for capability in worker.capabilities:

            self.workers[capability] = worker

    def get_worker(self, task_type):

        return self.workers.get(task_type)