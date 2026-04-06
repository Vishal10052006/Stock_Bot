# core/execution_engine.py

from core.router import Router
from core.executor import TaskExecutor
from intelligence.evaluation_engine import CriticAgent
from core.planner import TaskPlanner
from workers.worker_registry import WorkerRegistry
from workers.worker_loader import WorkerLoader
from core.decision_engine import DecisionEngine
from utils.logger import logger
import asyncio
from utils.formatter import format_success, format_error
from core.execution_trace import ExecutionTrace
from core.trace_logger import log_execution
from datetime import datetime
from core import executor
from memory.session_memory import SessionMemory

class ExecutionEngine:

    def __init__(self, trust_manager, memory_manager):
        self.trust_manager = trust_manager
        self.memory_manager = memory_manager
        self.registry = WorkerRegistry()
        loader = WorkerLoader(self.registry)
        loader.load_workers()
        self.router = Router(self.registry)
        self.executor = TaskExecutor()
        self.critic = CriticAgent()
        self.planner = TaskPlanner()
        self.decision_engine = DecisionEngine(self.memory_manager)

    async def run(self, command, memory_manager, worker_name, trust_manager):
        result = self.execute(command, worker_name, trust_manager)
        return [result]

    def execute(self, task, worker_name, trust_manager):

        worker = self.registry.get_worker(worker_name)

        if worker.name == "strategy_worker" and hasattr(self, "last_strategy"):
            result = self.last_strategy   # reuse instead of re-running
        else:
            result = worker.execute(task)

        # STORE RESULT (ONLY ONCE)
        success = result.get("success", True)
        confidence = result.get("confidence", 1.0)

        self.memory_manager.store({
            "type": "execution",
            "worker": worker.name,
            "task": task,
            "result": "SUCCESS" if success else "FAILED",
            "confidence": confidence
        })

        # TRUST UPDATE
        self.trust_manager.update_trust(worker.name, success, confidence)

        return result
    
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
            memory = self.memory_manager.load_memory()
            # Reduce trust dynamically
            past_failures = [
                m for m in memory
                if m.get("worker") == worker_name and m.get("result") == "FAILED"
            ]

            if len(past_failures) > 3:
                critic_score *= 0.7
            plan = self.planner.create_plan(command, memory)
            logger.info(f"Plan created: {plan}")

            final_outputs = []

            for step in plan:

                intent = step["intent"]
                task = step["task"]

                # GET WORKERS
                workers = self.registry.all_workers()

                # sort workers based on trust
                workers = sorted(
                    workers,
                    key=lambda w: self.trust_manager.get_trust(w.name),
                    reverse=True
                )

                # select BEST worker only
                best_worker = max(
                    workers,
                    key=lambda w: self.trust_manager.get_trust(w.name)
                )

                # execute ONLY best worker
                result = await self.executor.execute(
                    [best_worker],
                    intent,
                    task
                )

                outputs = [result]

                # CRITIC SCORING
                worker_outputs = []

                for worker, output in [(best_worker, outputs[0])]:

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

                memory = self.memory_manager.load_memory()

                bad_workers = [
                    m["worker"] for m in memory
                    if m.get("type") == "mistake"
                ]

                worker_outputs = [
                    w for w in worker_outputs
                    if w["worker"] not in bad_workers
                ]

                # safety fallback (VERY IMPORTANT)
                if not worker_outputs:
                    worker_outputs = [
                        {
                            "worker": worker.name,
                            "output": str(output),
                            "score": 0
                        }
                        for worker, output in zip(workers, outputs)
                    ]

                # BEST WORKER
                best_result = max(worker_outputs, key=lambda x: x["score"])
                worker_name = best_result["worker"]
                intent = intent  # already exists
                critic_score = best_result["score"]
                goal = intent  # temporary

                decision = self.decision_engine.make_decision(
                    worker_name=worker_name,
                    task_type=intent,
                    critic_score=critic_score,
                    goal=goal
                )

                result = best_result["output"]
                worker_name = best_result["worker"]
                critic_score = best_result["score"]

                # LOAD MEMORY
                memory = self.memory_manager.load_memory()

                # Reduce trust if worker failed many times
                past_failures = [
                    m for m in memory
                    if m.get("worker") == worker_name and m.get("result") == "FAILED"
                ]
                if len(past_failures) > 3:
                    critic_score *= 0.7

                # DECISION ENGINE
                decision = self.decision_engine.make_decision(
                    worker_name=worker_name,
                    task_type=intent,
                    critic_score=critic_score,
                    goal=goal
                )
                print("CONFIDENCE:", decision["confidence"])
                print("RISK:", decision["risk"])
                print("DECISION:", decision["decision"])

                # USER PREFERENCE CHECK
                user_rejections = [
                    m for m in memory
                    if m.get("type") == "user_preference"
                ]

                if len(user_rejections) > 2:
                    decision.decision = "ASK_USER"

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

                        # STORE USER PREFERENCE
                        self.memory_manager.add_memory({
                            "type": "user_preference",
                            "task": intent,
                            "preference": "rejected"
                        })

                        return format_error("Execution cancelled by user.")
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

                # MEMORY STORE
                memory_entry = {
                    "task": intent,
                    "worker": worker_name,
                    "decision": decision.decision,
                    "confidence": decision.confidence,
                    "result": "SUCCESS" if critic_score > 0 else "FAILED"
                }

                self.memory_manager.add_memory(memory_entry)

                # -------- STORE MISTAKES --------
                if critic_score == 0:
                    self.memory_manager.add_memory({
                        "type": "mistake",
                        "task": intent,
                        "worker": worker_name,
                        "issue": "low_score"
                    })

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
    


