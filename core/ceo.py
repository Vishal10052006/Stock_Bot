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

from core.trace_logger import log_execution
from core.execution_trace import ExecutionTrace
from datetime import datetime
class CEO:
    # Constructor (__init__)
    def __init__(self):
        self.registry = WorkerRegistry()

        loader = WorkerLoader(self.registry)
        loader.load_workers()

        self.memory = SessionMemory()
        self.router = TaskRouter(self.registry)
        self.executor = TaskExecutor()
        self.critic = CriticAgent()
        self.planner = TaskPlanner()

    # Plan Creation Function
    def create_plan(self, command: str):
        command_lower = command.lower()

        # Multi-command Splitting
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

        # Default single-step plan
        intents = self.router.detect(command)
        return [{
            "step": 1,
            "intent": intents[0] if intents else "writing",
            "task": command
        }]

    # Receive Command Function
    async def receive_command(self, command: str):
        try:
            # Expand Command Logic
            if command.lower() in ["expand it", "continue", "elaborate"]:
                last = self.memory.get_last_interaction()
                if last:
                    command = last["command"] + " (expanded)"

            # Planner
            plan = self.planner.create_plan(command)
            logger.info(f"Plan created: {plan}")

            final_outputs = []

            for step in plan:
                
                # Worker Selection
                intent = step["intent"]

                # ROUTER SELECTS WORKER
                worker = self.router.route(step["task"])

                if not worker:
                    final_outputs.append("No worker available.")
                    continue

                if intent == "general":
                    final_outputs.append("I don't know how to handle this task yet.")
                    continue

                # ----- RISK CONTROL -----

                # Safety Check
                if worker.risk_level == "high":
                    confirm = input(f"⚠ High risk task detected: {step['task']}. Continue? (yes/no): ")
                    if confirm.lower() != "yes":
                        return format_error("Execution cancelled by user.")

                # Critic Review (Medium Risk)
                if worker.risk_level == "medium":
                    review = self.critic.review(step["task"])
                    if review["decision"] == "reject":
                        return format_error("Critic rejected unsafe task.")

                # Decision Logging
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

                workers = self.registry.all_workers()

                import asyncio

                tasks = [
                    self.executor.execute(
                        [worker],
                        [intent],
                        step["task"]
                    )
                    for worker in workers
                ]

                outputs = await asyncio.gather(*tasks, return_exceptions=True)

                worker_outputs = []

                for worker, output in zip(workers, outputs):

                    if isinstance(output, Exception):
                        worker_outputs.append({
                            "worker": worker.name,
                            "output": str(output),
                            "score": 0
                        })
                    else:
                        score = self.critic.score(output)

                        worker_outputs.append({
                            "worker": worker.name,
                            "output": output,
                            "score": score
                        })

                best_result = max(worker_outputs, key=lambda x: x["score"])

                results = [best_result["output"]]

                worker_name = best_result["worker"]

                critic_score = best_result["score"]

                # Decision Engine
                decision = make_decision(
                    worker_name=worker_name,
                    task_type=task_type,
                    critic_score=critic_score
                )

                if len(plan) > 1:
                    task_type = step["intent"]
                else:
                    task_type = plan[0]["intent"].title()

                trace = ExecutionTrace(
                    task_type=task_type,
                    worker=worker_name,
                    confidence=decision.confidence,
                    risk=decision.risk,
                    decision=decision.decision,
                    result = "SUCCESS" if critic_score > 0 else "FAILED",
                    timestamp=str(datetime.now())
                )

                log_execution(trace)

                if results:
                    for result in results:
                        if isinstance(result, Exception):
                            final_outputs.append("Worker failed safely.")
                        else:
                            final_outputs.append(result)

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
                
                # Final Response
                final_response = format_success(
                    task_type,
                    "\n".join(final_outputs)
                )

            # Memory Storage
            self.memory.add_interaction(command, final_response)
            return final_response
        
        # Error Handling
        except Exception as e:
            logger.error(str(e))
            return format_error("Unexpected system failure.")
    
    def fallback_response(self, command):        # Fallback = Backup plan - Jab main system fail ho jaye, tab use hone wala option 
        return format_error("No suitable worker found.")
    
        
        task_type 
# print(CEO())
