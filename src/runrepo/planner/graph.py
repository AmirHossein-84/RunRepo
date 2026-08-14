"""Dependency Graph and Topological Sorter for ExecutionPlan steps."""

from collections import defaultdict, deque

from runrepo.planner.models import PlanStep


class PlanGraphError(Exception):
    """Base exception for planning graph construction and traversal errors."""
    pass


class PlanCycleError(PlanGraphError):
    """Raised when a dependency cycle is detected in the plan graph."""
    pass


class PlanGraph:
    """Directed Acyclic Graph (DAG) for managing step dependencies and deterministic ordering."""

    def __init__(self) -> None:
        self.steps: dict[str, PlanStep] = {}
        self.adj: dict[str, list[str]] = defaultdict(list)  # step_id -> list of steps that depend on it
        self.in_degree: dict[str, int] = defaultdict(int)

    def add_step(self, step: PlanStep) -> None:
        """Register a step in the graph."""
        if step.id in self.steps:
            raise PlanGraphError(f"Duplicate step ID '{step.id}' registered in plan graph")
        self.steps[step.id] = step
        # Initialize in-degree
        if step.id not in self.in_degree:
            self.in_degree[step.id] = 0

    def add_steps(self, steps: list[PlanStep]) -> None:
        """Register multiple steps."""
        for s in steps:
            self.add_step(s)

    def topological_sort(self) -> list[PlanStep]:
        """Perform topological sort on registered steps.

        Returns:
            Deterministic ordered list of PlanStep objects.

        Raises:
            PlanGraphError: If a step depends on an unregistered step ID.
            PlanCycleError: If a dependency cycle is detected.
        """
        # Build edges and compute in-degrees
        for step_id, step in self.steps.items():
            for dep_id in step.depends_on:
                if dep_id not in self.steps:
                    raise PlanGraphError(
                        f"Step '{step_id}' depends on unregistered step '{dep_id}'"
                    )
                self.adj[dep_id].append(step_id)
                self.in_degree[step_id] += 1

        # Queue nodes with in-degree 0
        queue: deque[str] = deque([sid for sid, step in self.steps.items() if self.in_degree[sid] == 0])
        sorted_steps: list[PlanStep] = []

        while queue:
            curr_id = queue.popleft()
            sorted_steps.append(self.steps[curr_id])

            for dependent_id in self.adj[curr_id]:
                self.in_degree[dependent_id] -= 1
                if self.in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        if len(sorted_steps) != len(self.steps):
            unresolved = [sid for sid, deg in self.in_degree.items() if deg > 0]
            raise PlanCycleError(
                f"Dependency cycle detected in plan graph involving steps: {', '.join(unresolved)}"
            )

        return sorted_steps
