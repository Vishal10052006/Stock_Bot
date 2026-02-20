from workers.writing_worker import WritingWorker
from workers.research_worker import ResearchWorker
import asyncio
from memory.session_memory import SessionMemory

class CEO:
    def __init__(self):
        self.workers = {
            "writing": WritingWorker(),
            "research": ResearchWorker()
        }
        self.memory = SessionMemory()
        print("[system] CEO Initialized")

    async def receive_command(self, command: str):

        if command.lower() in ["expand it", "continue", "elaborate"]:
            last = self.memory.get_last_interaction()
            if last:
                command = last["command"] + " (expanded)"

        intents = self.detect_multiple_intents(command)
        response = await self.route_tasks(intents, command)

        # Store interaction
        self.memory.add_interaction(command, response)

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
            results = await asyncio.gather(*tasks, return_exceptions=True)

            if all(isinstance(result, Exception) for result in results):
                return "All workers failed. Please try again."

            final_results = []

            for result in results:
                if isinstance(result, Exception):
                    final_results.append("Worker failed safely.")
                else:
                    final_results.append(result)

            return " | ".join(final_results)
    
    def fallback_response(self, command):        # Fallback = Backup plan - Jab main system fail ho jaye, tab use hone wala option 
        return f"No suitable worker found for: {command}"
        
        
# print(CEO())
