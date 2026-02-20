from workers.writing_worker import WritingWorker
from workers.research_worker import ResearchWorker
import asyncio
from memory.session_memory import SessionMemory
from utils.formatter import format_success, format_error
from utils.logger import log

class CEO:
    def __init__(self):
        self.workers = {
            "writing": WritingWorker(),
            "research": ResearchWorker()
        }
        self.memory = SessionMemory()
        print("[system] CEO Initialized")

    async def receive_command(self, command: str):
        try:
            if command.lower() in ["expand it", "continue", "elaborate"]:
                last = self.memory.get_last_interaction()
                if last:
                    command = last["command"] + " (expanded)"

            intents = self.detect_multiple_intents(command)
            response = await self.route_task(intents, command)

            self.memory.add_interaction(command, response)

            return response

        except Exception as e:
            log(f"ERROR: {str(e)}")
            return format_error("Unexpected system failure.")
    
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
                    final_results.append(format_error("Worker execution failed."))
                else:
                    final_results.append(result)

            combined = " | ".join(final_results)
            return format_success("Multi-Task", combined)
    
    def fallback_response(self, command):        # Fallback = Backup plan - Jab main system fail ho jaye, tab use hone wala option 
        return format_error("No suitable worker found.")
        
        
# print(CEO())
