import os
import importlib
import inspect
from workers.base_worker import BaseWorker


class WorkerLoader:

    def __init__(self, registry):
        self.registry = registry

    def load_workers(self):

        from config import SYSTEM_CONFIG

        workers_path = SYSTEM_CONFIG["workers_folder"]

        for filename in os.listdir(workers_path):

            # ignore non worker files
            if not filename.endswith("_worker.py"):
                continue

            module_name = filename[:-3]  # remove .py

            module = importlib.import_module(f"workers.{module_name}")

            for name, obj in inspect.getmembers(module):

                if inspect.isclass(obj) and issubclass(obj, BaseWorker) and obj != BaseWorker:

                    worker_instance = obj()

                    self.registry.register(worker_instance.name, worker_instance)

                    print(f"[WorkerLoader] Loaded worker: {worker_instance.name}")