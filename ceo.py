from workers.writing_worker import WritingWorker
from workers.research_worker import ResearchWorker

class CEO:
    def __init__(self):
        self.workers = {
            "writing": WritingWorker(),
            "research": ResearchWorker()
        }
        print("[system] CEO Initialized")

    def receive_command(self, command: str):
        intent = self.detect_intent(command)
        response = self.route_task(intent, command)
        return response
    
    def route_task(self, intent, command):

        if intent in self.workers:
            worker = self.workers[intent]
            return worker.execute(command)

        return self.fallback_response(command)
    
    def fallback_response(self, command):        # Fallback = Backup plan - Jab main system fail ho jaye, tab use hone wala option 
        return f"No suitable worker found for: {command}"
        
    def detect_intent(self, command: str):
        command = command.lower()

        routing_rules = {
            "writing": ["write", "blog", "content", "article"],
            "research": ["research", "find", "search", "info"]
        }
        for intent, keywords in routing_rules.items():
            for keyword in keywords:
                if keyword in command:
                    return intent

        return "general"
        
        
# print(CEO())
