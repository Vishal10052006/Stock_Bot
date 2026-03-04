from workers.writing_worker import WritingWorker
from workers.research_worker import ResearchWorker
import asyncio
from memory.session_memory import SessionMemory
from utils.formatter import format_success, format_error
from utils.logger import log
from core.router import TaskRouter
from core.executor import TaskExecutor
from core.critic import CriticAgent
from core.worker_registry import WorkerRegistry
from core.worker_loader import WorkerLoader

class CEO:
    def __init__(self):
        self.registry = WorkerRegistry()

        loader = WorkerLoader(self.registry)
        loader.load_workers()

        self.memory = SessionMemory()
        self.router = TaskRouter()
        self.executor = TaskExecutor()
        self.critic = CriticAgent()

    def create_plan(self, command: str):
        command_lower = command.lower()

        # Split compound commands
        if " and " in command_lower:
            parts = command.split(" and ")   # <-- use original command here

            plan = []
            step_number = 1

            for part in parts:
                intents = self.router.detect(part)
                intent = intents[0].lower() if intents else "writing"

                plan.append({
                    "step": step_number,
                    "intent": intent,
                    "task": part.strip()
                })

                step_number += 1

            return plan

        # Default single-step
        intents = self.router.detect(command)
        return [{
            "step": 1,
            "intent": intents[0] if intents else "writing",
            "task": command
        }]

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
                    self.registry.all_workers(),
                    intents,
                    step["task"]
                )
                print("EXECUTOR RESULTS:", results)

                if results:
                    for result in results:
                        if isinstance(result, Exception):
                            final_outputs.append("Worker failed safely.")
                        else:
                            final_outputs.append(result)

                if len(plan) > 1:
                    task_type = "Multi-Task plan"
                else:
                    task_type = plan[0]["intent"].title()

                # CRITIC CHECK START
                review = self.critic.review(plan, task_type, final_outputs)

                if review["decision"] == "reject":
                    final_response = format_error(
                        f"Critic rejected output: {review['reason']}"
                    )
                    return final_response

                elif review["decision"] == "retry":

                    # Retry once with refinement
                    refined_outputs = []

                    for step in plan:
                        intents = [step["intent"]]

                        print("PLAN STEP:", step)
                        print("WORKERS:", self.registry.all_workers().keys())
                        print("INTENTS:", intents)

                        results = await self.executor.execute(
                            self.registry.all_workers(),
                            intents,
                            step["task"]
                        )

                        if results:
                            for result in results:
                                if not isinstance(result, Exception):
                                    refined_outputs.append(result)

                    final_outputs = refined_outputs

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
    
    
        
        
# print(CEO())
