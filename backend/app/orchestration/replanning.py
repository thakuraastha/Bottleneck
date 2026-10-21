from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


PlanT = TypeVar("PlanT")


@dataclass(frozen=True)
class ReplanningResult(Generic[PlanT]):
    plan: PlanT
    passed: bool
    attempts: int
    issues: list[str]
    exhausted: bool


class BoundedReplanner(Generic[PlanT]):
    """Framework-neutral bounded loop used around planning and reflection agents."""

    def __init__(self, maximum_revisions: int = 2) -> None:
        if maximum_revisions < 0:
            raise ValueError("maximum_revisions cannot be negative")
        self.maximum_revisions = maximum_revisions

    def run(
        self,
        initial_plan: PlanT,
        reflect: Callable[[PlanT, int], tuple[bool, list[str], list[str]]],
        revise: Callable[[PlanT, list[str], int], PlanT],
    ) -> ReplanningResult[PlanT]:
        plan = initial_plan
        for revision in range(self.maximum_revisions + 1):
            passed, issues, guidance = reflect(plan, revision)
            if passed:
                return ReplanningResult(plan, True, revision, issues, False)
            if revision == self.maximum_revisions:
                return ReplanningResult(plan, False, revision, issues, True)
            plan = revise(plan, guidance, revision + 1)
        raise AssertionError("bounded replanning loop terminated unexpectedly")

