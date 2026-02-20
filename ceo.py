from workers.writing_worker import WritingWorker
from workers.research_worker import ResearchWorker
import asyncio
from memory.session_memory import SessionMemory
from utils.formatter import format_success, format_error
from utils.logger import log
from core.router import TaskRouter
from core.executor import TaskExecutor

class CEO:
    def __init__(self):
        self.workers = {
            "writing": WritingWorker(),
            "research": ResearchWorker()
        }
        self.memory = SessionMemory()
        self.router = TaskRouter()
        self.executor = TaskExecutor()
        print("[system] CEO Initialized")

    async def receive_command(self, command: str):
        try:
            if command.lower() in ["expand it", "continue", "elaborate"]:
                last = self.memory.get_last_interaction()
                if last:
                    command = last["command"] + " (expanded)"

            intents = self.router.detect(command)
            results = await self.executor.execute(self.workers, intents, command)

            if results is None:
                final_response = format_error("No suitable worker found.")
            else:
                final_outputs = []

                for result in results:
                    if isinstance(result, Exception):
                        final_outputs.append("Worker failed safely.")
                    else:
                        final_outputs.append(result)

                # 👇 ADD THIS HERE
                if len(intents) > 1:
                    task_type = "Multi-Task"
                else:
                    task_type = intents[0].capitalize()

                final_response = format_success(
                    task_type,
                    " | ".join(final_outputs)
                )

            self.memory.add_interaction(command, final_response)
            return final_response
        
        except Exception as e:
            log(f"ERROR: {str(e)}")
            return format_error("Unexpected system failure.")
    
    def fallback_response(self, command):        # Fallback = Backup plan - Jab main system fail ho jaye, tab use hone wala option 
        return format_error("No suitable worker found.")
        
        
# print(CEO())
