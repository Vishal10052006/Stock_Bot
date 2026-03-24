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
            # PLAN
            plan = self.planner.create_plan(command)
            logger.info(f"Plan created: {plan}")

            final_outputs = []

            for step in plan:

                intent = step["intent"]
                task = step["task"]

                # GET WORKERS
                workers = self.registry.all_workers()

                if not workers:
                    final_outputs.append("No workers available.")
                    continue

                # PARALLEL EXECUTION
                tasks = [
                    self.executor.execute([worker], [intent], task)
                    for worker in workers
                ]

                outputs = await asyncio.gather(*tasks, return_exceptions=True)

                # CRITIC SCORING
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

                # BEST WORKER
                best_result = max(worker_outputs, key=lambda x: x["score"])

                result = best_result["output"]
                worker_name = best_result["worker"]
                critic_score = best_result["score"]

                # DECISION ENGINE
                decision = make_decision(
                    worker_name=worker_name,
                    task_type=intent,
                    critic_score=critic_score
                )

                print("CONFIDENCE:", decision.confidence)
                print("RISK:", decision.risk)
                print("DECISION:", decision.decision)

                # PERMISSION ENGINE
                from core.autonomy_engine import check_permission

                permission = check_permission(intent)

                if permission == "BLOCK":
                    return format_error("Task blocked by autonomy rules.")

                elif permission == "ASK":
                    confirm = input("Permission required. Continue? (yes/no): ")
                    if confirm.lower() != "yes":
                        return format_error("Execution cancelled by user.")

                # DECISION CHECK
                if decision.decision == "BLOCK":
                    return format_error("Task blocked due to high risk.")

                elif decision.decision == "ASK_USER":
                    confirm = input("Decision requires approval. Proceed? (yes/no): ")
                    if confirm.lower() != "yes":
                        return format_error("Execution cancelled by user.")

                # STORE RESULT
                final_outputs.append(result)

                # TRACE LOGGING
                trace = ExecutionTrace(
                    task_type=intent,
                    worker=worker_name,
                    confidence=decision.confidence,
                    risk=decision.risk,
                    decision=decision.decision,
                    result="SUCCESS" if critic_score > 0 else "FAILED",
                    timestamp=str(datetime.now())
                )

                log_execution(trace)

            # FINAL CRITIC REVIEW
            review = self.critic.review(plan, intent, final_outputs)

            if review["decision"] == "reject":
                return format_error(f"Critic rejected output: {review['reason']}")

            elif review["decision"] == "retry":

                refined_outputs = []

                for step in plan:
                    workers = self.registry.all_workers()

                    results = await self.executor.execute(
                        workers,
                        [step["intent"]],
                        step["task"]
                    )

                    for r in results:
                        if not isinstance(r, Exception):
                            refined_outputs.append(r)

                final_outputs = refined_outputs

            # FINAL RESPONSE
            final_response = format_success(
                intent,
                "\n".join(final_outputs)
            )

            # MEMORY
            self.memory.add_interaction(command, final_response)

            return final_response

        except Exception as e:
            logger.error(str(e))
            return format_error("Unexpected system failure.")