class TaskRouter:

    def __init__(self, registry):
        self.registry = registry

    def detect(self, command: str):

        command = command.lower()
        intents = []

        workers = self.registry.all_workers()

        for name, worker in workers.items():

            for capability in worker.capabilities:

                if capability in command:
                    intents.append(name)
                    break

        if not intents:
            intents.append("general")

        return intents