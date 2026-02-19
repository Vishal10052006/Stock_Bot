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
        intent = self.process_command(command)           # intent means goal or purpose behind action
        response = self.generate_response(intent, command)
        return response

    def process_command(self, command: str):
        command = command.lower()

        if "write" in command:
            return "writing"
        
        elif "research" in command:
            return "research"
        
        else:
            return "general"
        
    def generate_response(self, intent, command):

        if intent in self.workers:
            worker = self.workers[intent]
            return worker.execute(command)

        return "General Command Received"

        
# print(CEO())
