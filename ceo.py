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

    def create_plan(self, command: str):
        command_lower = command.lower()

        # Rule-based multi-step planning
        if "create and publish" in command_lower:
            return [
                {"step": 1, "intent": "research", "task": "Research topic: " + command},
                {"step": 2, "intent": "writing", "task": "Write content"},
                {"step": 3, "intent": "writing", "task": "Optimize SEO"},
                {"step": 4, "intent": "writing", "task": "Publish blog"}
            ]

        # Default → single step plan
        intents = self.router.detect(command)
        return [
            {"step": 1, "intent": intents[0], "task": command}
        ]

    async def receive_command(self, command: str):
        try:
            if command.lower() in ["expand it", "continue", "elaborate"]:
                last = self.memory.get_last_interaction()
                if last:
                    command = last["command"] + " (expanded)"

            plan = self.create_plan(command)

            final_outputs = []

            for step in plan:
                intents = [step["intent"]]
                results = await self.executor.execute(
                    self.workers,
                    intents,
                    step["task"]
                )

                if results:
                    for result in results:
                        if isinstance(result, Exception):
                            final_outputs.append("Worker failed safely.")
                        else:
                            final_outputs.append(result)

                # 👇 ADD THIS HERE
                if len(plan) > 1:
                    task_type = "Multi-Task plan"
                else:
                    task_type = plan[0]["intent"].capitalize()

                final_response = format_success(
                    task_type,
                    "\n".join(final_outputs)
                )

            self.memory.add_interaction(command, final_response)
            return final_response
        
        except Exception as e:
            log(f"ERROR: {str(e)}")
            return format_error("Unexpected system failure.")
    
    def fallback_response(self, command):        # Fallback = Backup plan - Jab main system fail ho jaye, tab use hone wala option 
        return format_error("No suitable worker found.")
    
    def create_plan(self, command: str):
        command_lower = command.lower()

        # Example rule-based planning
        if "create and publish" in command_lower:
            return[
                {"step": 1, "intent": "research", "task": "Research topic"},
                {"step": 2, "intent": "writing", "task": "Writing content"},
                {"step": 3, "intent": "writing", "task": "Optimize SEO"},
                {"step": 4, "intent": "writing", "task": "Publish blog"}
            ]
        # Default: single step
        intents = self.router.detect(command)
        return[
            {"step": 1, "intent": intents[0], "task": command}
        ]
        
        
# print(CEO())
