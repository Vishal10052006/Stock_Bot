"""
Tests for the Phase 1 execution-engine boundary.
"""

import asyncio

from execution.execution_engine import ExecutionEngine


class FakeWorker:
    """Minimal worker used to verify the execution contract."""

    name = "fake_worker"

    def execute(self, task):
        """Return a valid Phase 1 worker result."""

        return {
            "success": True,
            "confidence": 0.9,
            "output": f"Executed: {task}",
        }


class FakeRegistry:
    """Registry containing one deterministic test worker."""

    def get_worker(self, worker_name):
        """Return the fake worker."""

        return FakeWorker()


class FakeLoader:
    """Prevent filesystem worker loading during this unit test."""

    def __init__(self, registry):
        self.registry = registry

    def load_workers(self):
        """No-op worker loading for the isolated test."""


class FakeReliabilityManager:
    """Capture reliability updates."""

    def __init__(self):
        self.calls = []

    def update(self, worker_name, success, confidence):
        """Record one reliability update."""

        self.calls.append(
            (worker_name, success, confidence)
        )


class FakeMemoryManager:
    """Capture persistent execution records."""

    def __init__(self):
        self.records = []

    def add_memory(self, record):
        """Record one memory entry."""

        self.records.append(record)


def test_execution_engine_normalizes_and_records_result(monkeypatch):
    """ExecutionEngine should normalize and persist a worker result."""

    reliability = FakeReliabilityManager()
    memory = FakeMemoryManager()

    monkeypatch.setattr(
        "execution.execution_engine.WorkerRegistry",
        FakeRegistry,
    )
    monkeypatch.setattr(
        "execution.execution_engine.WorkerLoader",
        FakeLoader,
    )

    engine = ExecutionEngine(
        trust_manager=None,
        memory_manager=memory,
        learning_engine=None,
        reinforcement_engine=None,
        reliability_manager=reliability,
    )

    result = asyncio.run(
        engine.run(
            "test task",
            "fake_worker",
        )
    )

    assert result["success"] is True
    assert result["confidence"] == 0.9
    assert result["worker"] == "fake_worker"

    assert reliability.calls == [
        ("fake_worker", True, 0.9)
    ]

    assert len(memory.records) == 1
    assert memory.records[0]["type"] == "execution"
    assert memory.records[0]["worker"] == "fake_worker"
    assert memory.records[0]["result"] == "SUCCESS"
    assert memory.records[0]["confidence"] == 0.9
