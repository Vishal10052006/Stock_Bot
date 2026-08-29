"""
Stock Bot — Executor

Executes selected workers and collects their results.

Worker contract:
    worker.execute(task) -> result

Workers may currently be synchronous. The executor also supports
awaitable results so asynchronous workers can be introduced later.
"""

import inspect


class Executor:
    """Execute selected workers and collect their results."""

    async def execute(self, workers, intents, command):
        """
        Execute workers selected by name.

        Args:
            workers: Mapping of worker name -> worker instance.
            intents: Iterable containing worker names.
            command: Task passed to each selected worker.

        Returns:
            List containing worker results or raised exceptions.
        """

        results = []

        for worker_name in intents:
            worker = workers.get(worker_name)

            # Ignore worker names that are not registered.
            if worker is None:
                continue

            try:
                # Current Stock Bot workers use synchronous execute().
                result = worker.execute(command)

                # Support asynchronous workers without changing the
                # public Executor contract.
                if inspect.isawaitable(result):
                    result = await result

                results.append(result)

            except Exception as exc:
                # Preserve the existing failure-isolation contract.
                results.append(exc)

        return results
