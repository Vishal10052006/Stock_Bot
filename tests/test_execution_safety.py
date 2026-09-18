from pathlib import Path

from execution.execution_engine import ExecutionEngine


def test_execution_engine_has_no_undefined_generic_dependencies():
    source = Path("execution/execution_engine.py").read_text()

    assert "self.router" not in source
    assert "self.planner" not in source
    assert "self.critic" not in source


def test_execution_engine_has_no_generic_command_orchestration():
    source = Path("execution/execution_engine.py").read_text()

    assert "def receive_command" not in source
    assert "def create_plan" not in source


def test_execution_engine_does_not_perform_reinforcement_learning():
    source = Path("execution/execution_engine.py").read_text()

    assert "reinforcement_engine.update(" not in source
    assert "calculate_reward(" not in source
    assert "get_reward(" not in source


def test_execution_engine_does_not_use_critic_scoring():
    source = Path("execution/execution_engine.py").read_text()

    assert "critic.score(" not in source
    assert "critic.review(" not in source


def test_execution_engine_does_not_use_generic_planning():
    source = Path("execution/execution_engine.py").read_text()

    assert "create_plan(" not in source
    assert "detect(" not in source


def test_execution_engine_has_single_execution_entrypoint():
    source = Path("execution/execution_engine.py").read_text()

    assert "async def run(" in source
    assert "def execute(" in source


def test_execution_engine_does_not_import_generic_planning_components():
    source = Path("execution/execution_engine.py").read_text()

    assert "from core.router" not in source
    assert "from core.planner" not in source
    assert "import Router" not in source
    assert "import TaskPlanner" not in source


def test_execution_engine_is_not_a_broker_execution_implementation():
    source = Path("execution/execution_engine.py").read_text()

    assert "place_order(" not in source
    assert "submit_order(" not in source
    assert "cancel_order(" not in source
    assert "modify_order(" not in source


def test_execution_engine_documents_financial_execution_boundary():
    source = Path("execution/execution_engine.py").read_text()

    assert "risk-approved trading decision" in source
    assert "broker orders" in source


def test_execution_engine_class_exists():
    assert ExecutionEngine is not None


def test_execution_engine_has_no_legacy_manager_constructor_dependencies():
    source = Path("execution/execution_engine.py").read_text()

    assert "trust_manager" not in source
    assert "memory_manager" not in source
    assert "learning_engine" not in source
    assert "reinforcement_engine" not in source
    assert "reliability_manager" not in source


def test_execution_engine_can_be_constructed_without_legacy_managers():
    engine = ExecutionEngine()

    assert engine is not None
    assert hasattr(engine, "registry")
