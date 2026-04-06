import asyncio

class TaskExecutor:

    async def execute(self, workers, intents, command):
        tasks = []

        for intent in intents:
            if intent in workers:
                worker = workers[intent]
                tasks.append(worker.execute(command))

        if not tasks:
            return None

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results