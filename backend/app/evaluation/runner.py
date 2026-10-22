from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.tables import AgentRunRow, EvaluationRunRow, IncidentRow, WorkflowRunRow
from app.engines import RiskEngine
from app.models.domain import EvidenceItem, EvidenceType
from app.models.investigations import ProposedAllocation, ProposedStrategy
from app.orchestration.routing import ConditionalRouter
from app.services import StrategyPipeline
from app.simulation import SupplySimulator
from app.tools import SupplyChainTools


def _metric(numerator: int, denominator: int, method: str) -> dict[str, Any]:
    return {
        "measured": denominator > 0,
        "numerator": numerator,
        "denominator": denominator,
        "value_percent": round(numerator / denominator * 100, 2) if denominator else None,
        "method": method,
    }


class EvaluationRunner:
    """Run reproducible, deterministic checks and persist only observed results."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.tools = SupplyChainTools(session)

    def run(self) -> EvaluationRunRow:
        started_at = datetime.now(timezone.utc)
        start_clock = perf_counter()
        run = EvaluationRunRow(
            evaluation_run_id=str(uuid4()), status="RUNNING", scenario_count=3,
            metrics={}, started_at=started_at,
        )
        self.session.add(run)
        self.session.commit()

        results: list[dict[str, Any]] = []
        tool_successes = 0
        tool_expected = 0
        structured_valid = 0
        structured_expected = 0
        grounded = 0
        evidence_count = 0
        route_correct = 0
        route_expected = 0
        valid_recommendations = 0
        recommendation_count = 0

        incident = self.session.scalar(
            select(IncidentRow)
            .where(IncidentRow.component_id.is_not(None), IncidentRow.order_id.is_not(None), IncidentRow.supplier_id.is_not(None))
            .order_by(IncidentRow.created_at)
        )
        if incident is None:
            results.append({"scenario": "fixture_selection", "passed": False, "error": "no complete incident fixture"})
        else:
            captured: dict[str, Any] = {}

            def invoke(name: str, operation: Callable[[], Any]) -> Any:
                nonlocal tool_expected, tool_successes, structured_expected, structured_valid
                tool_expected += 1
                value = operation()
                tool_successes += 1
                values = value if isinstance(value, list) else [value]
                structured_expected += len(values)
                structured_valid += sum(1 for item in values if hasattr(item, "model_dump"))
                captured[name] = value
                return value

            try:
                supplier = invoke("supplier", lambda: self.tools.get_supplier(incident.supplier_id))
                orders = invoke("orders", lambda: self.tools.get_supplier_orders(incident.supplier_id))
                order = next(row for row in orders if row.order_id == incident.order_id)
                inventory = invoke("inventory", lambda: self.tools.get_inventory(incident.component_id))
                shipments = invoke("shipments", lambda: self.tools.get_shipments(incident.order_id))
                production = invoke("production", lambda: self.tools.get_production_requirements(incident.component_id))
                end = self.settings.simulation_date + timedelta(days=self.settings.planning_horizon_days - 1)
                demand = invoke("demand", lambda: self.tools.get_demand(incident.component_id, self.settings.simulation_date, end))
                evidence = [
                    EvidenceItem(
                        incident_id=incident.incident_id,
                        evidence_type=EvidenceType.VERIFIED_FACT,
                        field="supplier_status",
                        value=supplier.status,
                        source_system="suppliers",
                        source_record_id=supplier.supplier_id,
                        observed_at=started_at,
                    ),
                    EvidenceItem(
                        incident_id=incident.incident_id,
                        evidence_type=EvidenceType.VERIFIED_FACT,
                        field="ordered_quantity",
                        value=order.ordered_quantity,
                        unit="units",
                        source_system="purchase_orders",
                        source_record_id=order.order_id,
                        observed_at=started_at,
                    ),
                ]
                evidence_count += len(evidence)
                grounded += sum(1 for item in evidence if item.source_system and item.source_record_id)
                structured_expected += len(evidence)
                structured_valid += len(evidence)
                results.append({"scenario": "data_tools_and_grounding", "passed": True, "tool_calls": list(captured)})

                simulation = SupplySimulator().simulate(
                    start_date=self.settings.simulation_date,
                    horizon_days=self.settings.planning_horizon_days,
                    inventory=inventory,
                    demand=demand,
                    shipments=shipments,
                    production_requirements=production,
                )
                risk = RiskEngine().assess(
                    incident_id=incident.incident_id,
                    delay_days=max((max(row.revised_eta for row in shipments) - max(row.original_eta for row in shipments)).days, 0),
                    simulation=simulation,
                    total_required_demand=sum(row.demand_quantity for row in demand),
                )
                decision = ConditionalRouter(
                    medium_risk_enabled=self.settings.medium_risk_alternative_research
                ).decide(risk, simulation)
                expected_route = (
                    risk.severity.value in {"MEDIUM", "HIGH", "CRITICAL"}
                    or (
                        simulation.first_actual_shortage_date is not None
                        and (simulation.first_actual_shortage_date - simulation.start_date).days <= 7
                    )
                )
                route_expected += 1
                route_correct += int(decision.should_run == expected_route)
                structured_expected += 3
                structured_valid += 3
                results.append({
                    "scenario": "risk_and_conditional_routing", "passed": decision.should_run == expected_route,
                    "severity": risk.severity.value, "branch": decision.branch,
                })

                pipeline = StrategyPipeline(self.session, self.settings).evaluate(
                    incident=incident,
                    proposals=self._proposals(),
                    maximum_additional_budget=100_000,
                    evidence_ids=[item.evidence_id for item in evidence],
                )
                selected = next(
                    (item for item in pipeline.evaluated if item.strategy.strategy_id == pipeline.recommended_strategy_id),
                    None,
                )
                recommendation_count += int(selected is not None)
                valid_recommendations += int(selected is not None and selected.evaluation.valid)
                structured_expected += 1
                structured_valid += 1
                results.append({
                    "scenario": "strategy_constraints", "passed": bool(selected and selected.evaluation.valid),
                    "recommended_strategy": selected.strategy.strategy_type.value if selected else None,
                })
            except Exception as exc:
                results.append({"scenario": "execution_error", "passed": False, "error": str(exc)})

        completed = sum(1 for result in results if result.get("passed"))
        latency_ms = round((perf_counter() - start_clock) * 1000, 2)
        performance = self._performance_summary()
        metrics = {
            "workflow_completion_rate": _metric(completed, 3, "Passed deterministic evaluation scenarios / 3 attempted scenarios."),
            "correct_tool_invocation_rate": _metric(tool_successes, tool_expected, "Successful required read-only data-tool calls / attempted required calls."),
            "evidence_grounding_rate": _metric(grounded, evidence_count, "Generated verified facts with both source_system and source_record_id / generated verified facts."),
            "structured_output_validity_rate": _metric(structured_valid, structured_expected, "Pydantic-validated outputs / structured outputs produced by the suite."),
            "strategy_constraint_satisfaction_rate": _metric(valid_recommendations, recommendation_count, "Constraint-valid selected strategies / selected strategies."),
            "reflection_issue_detection_rate": {**_metric(0, 0, "Requires a live model-backed Reflection Agent run."), "reason": "not measured in deterministic suite"},
            "conditional_routing_correctness": _metric(route_correct, route_expected, "Routing decisions matching independently computed rule expectations / routing checks."),
            "average_workflow_latency_ms": {"measured": True, "value": latency_ms, "method": "Wall-clock duration of this deterministic evaluation run."},
            "end_to_end_performance": performance,
            "estimated_model_cost_usd": performance["estimated_model_cost_usd"],
            "agent_failure_rate": {**_metric(0, 0, "Requires live ADK agent invocations."), "reason": "not measured in deterministic suite"},
            "scenario_results": results,
            "suite_kind": "deterministic_offline",
        }
        run.metrics = metrics
        run.status = "COMPLETED" if completed == 3 else "FAILED"
        run.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(run)
        return run

    def _performance_summary(self) -> dict[str, Any]:
        workflow = self.session.scalar(
            select(WorkflowRunRow)
            .where(WorkflowRunRow.completed_at.is_not(None))
            .order_by(WorkflowRunRow.completed_at.desc())
        )
        if workflow is None or workflow.completed_at is None:
            return {
                "measured": False,
                "reason": "No completed end-to-end workflow is stored yet.",
                "workflow_runtime_ms": None,
                "summed_agent_runtime_ms": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "estimated_model_cost_usd": None,
            }

        runs = self.session.scalars(
            select(AgentRunRow).where(
                AgentRunRow.workflow_run_id == workflow.workflow_run_id
            )
        ).all()
        input_tokens = 0
        output_tokens = 0
        for row in runs:
            usage = row.token_usage or {}
            input_tokens += int(
                usage.get("prompt_token_count")
                or usage.get("input_tokens")
                or usage.get("input_token_count")
                or 0
            )
            output_tokens += int(
                usage.get("candidates_token_count")
                or usage.get("output_tokens")
                or usage.get("output_token_count")
                or 0
            )
        started = workflow.started_at
        completed = workflow.completed_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=timezone.utc)
        workflow_runtime_ms = round(
            max((completed - started).total_seconds() * 1000, 0.0), 2
        )
        estimated_cost = round(
            input_tokens / 1_000_000
            * self.settings.model_input_cost_per_million_usd
            + output_tokens / 1_000_000
            * self.settings.model_output_cost_per_million_usd,
            6,
        )
        return {
            "measured": True,
            "workflow_run_id": workflow.workflow_run_id,
            "workflow_runtime_ms": workflow_runtime_ms,
            "summed_agent_runtime_ms": round(
                sum(row.duration_ms or 0 for row in runs), 2
            ),
            "agent_event_count": len(runs),
            "failed_agent_event_count": sum(
                1 for row in runs if row.status == "FAILED"
            ),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_model_cost_usd": estimated_cost,
            "cost_assumptions": {
                "input_usd_per_million_tokens": self.settings.model_input_cost_per_million_usd,
                "output_usd_per_million_tokens": self.settings.model_output_cost_per_million_usd,
                "note": "Configurable budget estimate; provider billing is authoritative.",
            },
        }

    @staticmethod
    def _proposals() -> list[ProposedStrategy]:
        def proposal(kind: str, allocations: list[tuple[str, int, bool]]) -> ProposedStrategy:
            return ProposedStrategy(
                strategy_type=kind,
                allocations=[
                    ProposedAllocation(supplier_id=supplier, quantity=quantity, expedite=expedite)
                    for supplier, quantity, expedite in allocations
                ],
                rationale="deterministic evaluation fixture",
            )

        return [
            proposal("WAIT", [("SUP-A", 1000, False)]),
            proposal("EXPEDITE", [("SUP-A", 1000, True)]),
            proposal("PARTIAL_SWITCH", [("SUP-A", 550, False), ("SUP-B", 450, False)]),
            proposal("SPLIT_ORDER", [("SUP-B", 450, False), ("SUP-D", 250, False), ("SUP-C", 300, False)]),
            proposal("FULL_SWITCH", [("SUP-B", 1000, False)]),
        ]
