import json

MEMORY_FILE = "memory/long_term_memory.json"


class MemoryManager:

    def load_memory(self):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []

    def save_memory(self, data):
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def add_memory(self, entry):
        memory = self.load_memory()
        memory.append(entry)
        self.save_memory(memory)

    def store_worker_performance(self, worker, success, confidence):
        self.memory.append({
            "type": "worker_performance",
            "worker": worker,
            "success": success,
            "confidence": confidence
        })

    def store(self, data):
        if not hasattr(self, "memory"):
            self.memory = []

        self.memory.append(data)