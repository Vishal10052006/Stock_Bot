from workers.writing_worker import WritingWorker
from workers.research_worker import ResearchWorker
import asyncio

class CEO:
    def __init__(self):
        self.workers = {
            "writing": WritingWorker(),
            "research": ResearchWorker()
        }
        print("[system] CEO Initialized")

    async def receive_command(self, command: str):
        intents = self.detect_multiple_intents(command)
        response = await self.route_tasks(intents, command)
        return response
    
    def detect_multiple_intents(self, command: str):
        command = command.lower()
        intents = []

        routing_rules = {
            "writing": ["write", "blog", "content", "article"],
            "research": ["research", "find", "search", "info"]
        }
        for intent, keywords in routing_rules.items():
            for keyword in keywords:
                if keyword in command:
                    intents.append(intent)

        if not intents:
            intents.append("general")

        return intents
    
    async def route_task(self, intents, command):

        tasks = []

        for intent in intents:
            if intent in self.workers:
                worker = self.workers[intent]
                tasks.append(worker.execute(command))

        if tasks:
            results = await asyncio.gather(*tasks)
            return " | ".join(results)
        
        return self.fallback_response(command)
    
    async def route_tasks(self, intents, command):
        responses = []
        for intent in intents:
            if intent in self.workers:
                worker = self.workers[intent]
                response = await worker.execute(command)
                responses.append(response)
            else:
                responses.append(self.fallback_response(command))
        return responses
    
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
