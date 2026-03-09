class Router:

    def __init__(self, registry):

        self.registry = registry

    def route(self, task):

        task_type = task["type"]

        worker = self.registry.get_worker(task_type)

        return worker