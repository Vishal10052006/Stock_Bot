class SessionMemory:
    def __init__(self):
        self.history = []

    def add_interaction(self, command, response):
        self.history.append({
            "command": command,
            "response": response
        })

    def get_last_interaction(self):
        if self.history:
            return self.history[-1]
        return None

    def get_all_history(self):
        return self.history