"""
Phase 2 tests for the TaskPlanner contract.

The planner is responsible only for converting a user command
into an ordered execution plan.

It must not select workers or execute tasks.
"""

from core.planner import TaskPlanner


def test_planner_creates_ordered_blog_workflow():
    """Blog commands should produce the expected ordered workflow."""

    planner = TaskPlanner()

    plan = planner.create_plan("Write a blog about AI")

    assert isinstance(plan, list)
    assert len(plan) == 5

    assert [step["step"] for step in plan] == [1, 2, 3, 4, 5]

    assert [step["intent"] for step in plan] == [
        "research",
        "writing",
        "writing",
        "writing",
        "writing",
    ]


def test_planner_creates_research_workflow():
    """Research commands should create a research workflow."""

    planner = TaskPlanner()

    plan = planner.create_plan("Research artificial intelligence")

    assert len(plan) == 2

    assert plan[0]["intent"] == "research"
    assert plan[1]["intent"] == "writing"


def test_planner_creates_default_workflow():
    """Unknown commands should receive a single-step workflow."""

    planner = TaskPlanner()

    plan = planner.create_plan("Analyze market conditions")

    assert len(plan) == 1
    assert plan[0]["step"] == 1
    assert plan[0]["intent"] == "writing"


def test_planner_preserves_step_order_without_memory():
    """The planner should preserve workflow order without memory."""

    planner = TaskPlanner()

    plan = planner.create_plan("Write a blog about stocks")

    assert [step["step"] for step in plan] == [1, 2, 3, 4, 5]
