import json
import os

class SessionMemory:

    def __init__(self, filename="memory_store.json"):
        self.filename = filename
        self.history = []
        self._load_from_file()

    def add_interaction(self, command, response):
        interaction = {
            "command": command,
            "response": response
        }

        self.history.append(interaction)
        self._save_to_file()

    def get_last_interaction(self):
        if self.history:
            return self.history[-1]
        return None

    def get_all_history(self):
        return self.history

    # -----------------------
    # Private Methods
    # -----------------------

    def _save_to_file(self):
        with open(self.filename, "w") as f:
            json.dump(self.history, f, indent=4)

    def _load_from_file(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                try:
                    self.history = json.load(f)
                except json.JSONDecodeError:
                    self.history = []