class TaskRouter:
    def __init__(self):
        self.routing_rules = {
            "writing": ["write", "blog", "article"],
            "research": ["research", "find", "search", "info"]
        }

    def detect(self, command: str):
        command = command.lower()
        intents = []

        for intent, keywords in self.routing_rules.items():
            for keyword in keywords:
                if keyword in command:
                    intents.append(intent)
                    break

        if not intents:
            intents.append("general")

        return intents