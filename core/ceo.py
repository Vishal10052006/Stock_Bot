from core import executor
from workers.writing_worker import WritingWorker
from workers.research_worker import ResearchWorker
import asyncio
from memory.session_memory import SessionMemory
from utils.formatter import format_success, format_error
from utils.logger import logger
from core.router import TaskRouter
from core.executor import TaskExecutor
from core.critic import CriticAgent
from core.worker_registry import WorkerRegistry
from core.worker_loader import WorkerLoader
from core.planner import TaskPlanner
from core.decision_engine import make_decision

class CEO:
    def __init__(self):
        self.registry = WorkerRegistry()

        loader = WorkerLoader(self.registry)
        loader.load_workers()

        self.memory = SessionMemory()
        self.router = TaskRouter(self.registry)
        self.executor = TaskExecutor()
        self.critic = CriticAgent()
        self.planner = TaskPlanner()

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

            plan = self.planner.create_plan(command)
            logger.info(f"Plan created: {plan}")

            final_outputs = []

            for step in plan:

                intent = step["intent"]
                worker = self.registry.get_worker(intent)

                if not worker:
                    final_outputs.append("No worker available.")
                    continue

                if intent == "general":
                    final_outputs.append("I don't know how to handle this task yet.")
                    continue

                # ----- RISK CONTROL -----

                if worker.risk_level == "high":
                    confirm = input(f"⚠ High risk task detected: {step['task']}. Continue? (yes/no): ")
                    if confirm.lower() != "yes":
                        return format_error("Execution cancelled by user.")

                if worker.risk_level == "medium":
                    review = self.critic.review(step["task"])
                    if review["decision"] == "reject":
                        return format_error("Critic rejected unsafe task.")

                decision = make_decision(
                    worker_name="blog_writer",
                    task_type="write_blog",
                    critic_score=0.85
                )
                print("CONFIDENCE:", decision.confidence)
                print("RISK:", decision.risk)
                print("DECISION:", decision.decision)

                if decision.decision == "AUTO_EXECUTE":
                    executor.run()

                elif decision.decision == "ASK_USER":
                    user_input = input("❓ Decision requires user approval. Proceed? (yes/no): ")
                    if user_input.lower() == "yes":
                        executor.run()
                    else:
                        return format_error("Execution cancelled by user.")

                else:
                    print("Task blocked due to high risk.")

                # ----- EXECUTE -----

                results = await self.executor.execute(
                    self.registry.all_workers(),
                    [intent],
                    step["task"]
                )

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
            logger.error(str(e))
            return format_error("Unexpected system failure.")
    
    def fallback_response(self, command):        # Fallback = Backup plan - Jab main system fail ho jaye, tab use hone wala option 
        return format_error("No suitable worker found.")
    
    
        
        
# print(CEO())
