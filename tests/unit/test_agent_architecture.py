# pyrefly: ignore [missing-import]
from google.adk.agents import LlmAgent
# pyrefly: ignore [missing-import]
from google.adk.workflow import JoinNode, Workflow

from app.agents import build_agent_catalog
from app.crews import build_supplier_research_crew
from app.orchestration import build_investigation_workflow


def test_exactly_nine_top_level_agents_are_defined() -> None:
    catalog = build_agent_catalog("gemini-2.5-flash")
    assert len(catalog.top_level_agents) == 9
    assert len({agent.name for agent in catalog.top_level_agents}) == 9
    assert all(isinstance(agent, LlmAgent) for agent in catalog.top_level_agents)


def test_four_specialists_use_real_adk_fan_out_join_workflow_and_namespaced_outputs() -> None:
    catalog = build_agent_catalog("gemini-2.5-flash")
    workflow = catalog.parallel_investigation
    assert isinstance(workflow, Workflow)
    assert workflow.max_concurrency == 4
    graph = workflow.graph
    specialist_names = {
        "supplier_intelligence_agent", "logistics_intelligence_agent",
        "demand_inventory_agent", "production_impact_agent",
    }
    nodes_by_name = {node.name: node for node in graph.nodes}
    assert specialist_names.issubset(nodes_by_name)
    assert isinstance(nodes_by_name["investigation_evidence_join"], JoinNode)
    keys = {
        catalog.supplier_intelligence.output_key,
        catalog.logistics_intelligence.output_key,
        catalog.demand_inventory.output_key,
        catalog.production_impact.output_key,
    }
    assert keys == {
        "investigation_supplier",
        "investigation_logistics",
        "investigation_inventory",
        "investigation_production",
    }


def test_investigation_workflow_triages_before_parallel_stage() -> None:
    workflow = build_investigation_workflow("gemini-2.5-flash")
    assert isinstance(workflow.root, Workflow)
    graph = workflow.root.graph
    node_names = {node.name for node in graph.nodes}
    assert "orchestrator_triage_agent" in node_names
    assert "parallel_investigation" in node_names


def test_nested_supplier_crew_has_required_roles_and_structured_review() -> None:
    crew = build_supplier_research_crew("gemini-2.5-flash")
    assert [agent.role for agent in crew.agents] == ["Supplier Researcher", "Supplier Analyst", "Supplier Reviewer"]
    assert [task.name for task in crew.tasks] == [
        "retrieve_supplier_candidates",
        "compare_supplier_candidates",
        "review_supplier_candidates",
    ]
    assert crew.tasks[-1].output_pydantic.__name__ == "SupplierResearchResult"
