"""Unit tests for PlanGraph and topological sorting."""

import pytest
from runrepo.planner.graph import PlanCycleError, PlanGraph, PlanGraphError
from runrepo.planner.models import ActionType, PlanStep, RiskLevel


def _make_step(step_id: str, depends_on: list[str] | None = None) -> PlanStep:
    return PlanStep(
        id=step_id,
        description=f"Step {step_id}",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        depends_on=depends_on or [],
        risk=RiskLevel.SAFE,
        reason="test",
    )


def test_plan_graph_linear_ordering():
    graph = PlanGraph()
    step_a = _make_step("a")
    step_b = _make_step("b", depends_on=["a"])
    step_c = _make_step("c", depends_on=["b"])

    # Add out of order
    graph.add_steps([step_c, step_a, step_b])
    sorted_steps = graph.topological_sort()

    ids = [s.id for s in sorted_steps]
    assert ids == ["a", "b", "c"]


def test_plan_graph_branching_dag():
    graph = PlanGraph()
    root = _make_step("root")
    node_a = _make_step("node_a", depends_on=["root"])
    node_b = _make_step("node_b", depends_on=["root"])
    leaf = _make_step("leaf", depends_on=["node_a", "node_b"])

    graph.add_steps([leaf, node_b, node_a, root])
    sorted_steps = graph.topological_sort()
    ids = [s.id for s in sorted_steps]

    assert ids[0] == "root"
    assert ids[3] == "leaf"
    assert "node_a" in (ids[1], ids[2])
    assert "node_b" in (ids[1], ids[2])


def test_plan_graph_cycle_detection():
    graph = PlanGraph()
    step_a = _make_step("a", depends_on=["b"])
    step_b = _make_step("b", depends_on=["a"])

    graph.add_steps([step_a, step_b])
    with pytest.raises(PlanCycleError) as exc_info:
        graph.topological_sort()
    assert "Dependency cycle detected" in str(exc_info.value)


def test_plan_graph_unregistered_dependency():
    graph = PlanGraph()
    step_a = _make_step("a", depends_on=["missing_prereq"])

    graph.add_step(step_a)
    with pytest.raises(PlanGraphError) as exc_info:
        graph.topological_sort()
    assert "depends on unregistered step 'missing_prereq'" in str(exc_info.value)
