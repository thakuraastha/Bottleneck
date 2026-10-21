from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
import streamlit as st

from frontend.components.api import ApiError, BottleneckApi
from frontend.components.ui import badge, empty_state, format_currency, page_header


def _incidents(api: BottleneckApi) -> list[dict]:
    return api.get("/incidents")


def _selected_incident(api: BottleneckApi) -> dict | None:
    incidents = _incidents(api)
    if not incidents:
        empty_state("No incidents", "Create a disruption event to begin an investigation.")
        return None
    options = {f"{row['title']} · {row['incident_id'][:8]}": row for row in incidents}
    current = st.session_state.get("selected_incident_label")
    index = list(options).index(current) if current in options else 0
    label = st.selectbox("Incident", list(options), index=index, key="selected_incident_label")
    return options[label]


def executive(api: BottleneckApi) -> None:
    page_header("Executive dashboard", "Current disruption queue and modeled operational exposure.")
    summary = api.get("/dashboard/summary")
    cols = st.columns(6)
    values = [
        ("Active incidents", summary["active_incidents"]),
        ("Critical", summary["critical_incidents"]),
        ("Pending approval", summary["pending_approvals"]),
        ("Modeled exposure", format_currency(summary["estimated_financial_exposure"])),
        ("Downtime days", f"{summary['estimated_downtime_days']:,.1f}"),
        ("Completed runs", summary["completed_investigations"]),
    ]
    for column, (label, value) in zip(cols, values):
        column.metric(label, value)
    st.caption("Synthetic scenario data; exposure and downtime are modeled estimates, not observed business results.")
    st.subheader("Recent disruptions")
    rows = summary["recent_disruptions"]
    if rows:
        st.dataframe(pd.DataFrame(rows)[["title", "event_type", "supplier_id", "component_id", "status", "updated_at"]], width="stretch", hide_index=True)
    else:
        empty_state("No recent disruptions", "The event queue is empty.")


def create_incident(api: BottleneckApi) -> None:
    page_header("Create incident", "Submit a typed event; duplicate operations are blocked by idempotency key.")
    with st.form("create-incident"):
        event_type = st.selectbox("Event type", ["SUPPLIER_DELAY", "INVENTORY_ALERT", "SHIPMENT_DELAY", "QUALITY_FAILURE", "SUPPLIER_CAPACITY_FAILURE", "PRICE_INCREASE", "MANUAL_INCIDENT"])
        col1, col2, col3 = st.columns(3)
        supplier_id = col1.text_input("Supplier ID", "SUP-A")
        component_id = col2.text_input("Component ID", "MOTOR-X7")
        order_id = col3.text_input("Order ID", "PO-X7-1001")
        title = st.text_input("Title", "Motor X7 supplier delay")
        description = st.text_area("Description", "Supplier A reported a 10-day delivery delay.")
        idempotency_key = st.text_input("Idempotency key", f"manual-{uuid4()}")
        submitted = st.form_submit_button("Create incident", type="primary")
    if submitted:
        payload = {
            "event_id": str(uuid4()), "event_type": event_type, "source_system": "streamlit_dashboard",
            "entity_id": order_id or component_id or supplier_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {key: value for key, value in {
                "supplier_id": supplier_id, "component_id": component_id, "order_id": order_id,
                "title": title, "description": description,
            }.items() if value},
            "idempotency_key": idempotency_key,
        }
        result = api.post("/events", payload)
        st.success(f"Incident {result['incident_id']} {'reused' if result['duplicate'] else 'created'}.")


def active_incidents(api: BottleneckApi) -> None:
    page_header("Active incidents", "Operational queue for investigation, escalation, and approval.")
    rows = _incidents(api)
    if not rows:
        empty_state("No active incidents", "Create an incident to populate the queue.")
        return
    statuses = sorted({row["status"] for row in rows})
    selected = st.multiselect("Status", statuses, default=statuses)
    filtered = [row for row in rows if row["status"] in selected]
    st.dataframe(pd.DataFrame(filtered)[["title", "event_type", "supplier_id", "component_id", "order_id", "status", "detected_at"]], width="stretch", hide_index=True)


def investigation(api: BottleneckApi) -> None:
    page_header("Incident investigation", "Verified source records and deterministic material-flow consequences.")
    incident = _selected_incident(api)
    if not incident:
        return
    st.markdown(badge(incident["status"]), unsafe_allow_html=True)
    a, b, c, d = st.columns(4)
    a.metric("Supplier", incident.get("supplier_id") or "Unknown")
    b.metric("Component", incident.get("component_id") or "Unknown")
    c.metric("Order", incident.get("order_id") or "Unknown")
    d.metric("Event", incident["event_type"].replace("_", " "))
    simulation = api.get(f"/incidents/{incident['incident_id']}/simulation")
    cols = st.columns(5)
    cols[0].metric("Safety-stock breach", simulation["first_safety_stock_breach_date"] or "None")
    cols[1].metric("Actual shortage", simulation["first_actual_shortage_date"] or "None")
    cols[2].metric("Shortage units", f"{simulation['total_shortage_quantity']:,}")
    cols[3].metric("Downtime days", f"{simulation['estimated_downtime_days']:,.1f}")
    cols[4].metric("Modeled exposure", format_currency(simulation["financial_exposure"]))
    timeline = pd.DataFrame(simulation["daily_projection"])
    if not timeline.empty:
        timeline["date"] = pd.to_datetime(timeline["date"])
        st.line_chart(timeline.set_index("date")[["projected_ending_stock", "safety_stock"]], color=["#38bdf8", "#f59e0b"])
        with st.expander("Daily simulation records"):
            st.dataframe(timeline, width="stretch", hide_index=True)


def workflow(api: BottleneckApi) -> None:
    page_header("Live agent workflow", "Persisted execution events only—no decorative or fabricated agent activity.")
    incident = _selected_incident(api)
    if not incident:
        return
    if st.button("Run live investigation", type="primary"):
        with st.spinner("Running ADK triage and parallel specialist investigation…"):
            api.post(f"/incidents/{incident['incident_id']}/run", {})
        st.success("Investigation completed and execution events were persisted.")
    data = api.get(f"/incidents/{incident['incident_id']}/workflow")
    if not data["workflow_runs"]:
        empty_state("Workflow has not run", "Configure GOOGLE_API_KEY or GEMINI_API_KEY, then start the live investigation.")
        return
    st.dataframe(pd.DataFrame(data["workflow_runs"]), width="stretch", hide_index=True)
    if data["agent_runs"]:
        st.subheader("Agent and tool timeline")
        st.dataframe(pd.DataFrame(data["agent_runs"]), width="stretch", hide_index=True)


def evidence(api: BottleneckApi) -> None:
    page_header("Evidence explorer", "Trace verified, calculated, and inferred claims to their source records.")
    incident = _selected_incident(api)
    if not incident:
        return
    rows = api.get(f"/incidents/{incident['incident_id']}/evidence")
    if not rows:
        empty_state("No aggregated evidence", "Evidence appears after a completed specialist investigation.")
        return
    frame = pd.DataFrame(rows)
    for tab, kind in zip(st.tabs(["Verified", "Calculated", "Inferred"]), ["VERIFIED_FACT", "CALCULATED_FACT", "INFERRED_RISK"]):
        with tab:
            st.dataframe(frame[frame["evidence_type"] == kind], width="stretch", hide_index=True)


def risk(api: BottleneckApi) -> None:
    page_header("Risk analysis", "Deterministic business index; it is not a probability of disruption.")
    incident = _selected_incident(api)
    if not incident:
        return
    row = api.get(f"/incidents/{incident['incident_id']}/risk")
    if row is None:
        empty_state("Risk not assessed", "The risk engine runs after evidence aggregation and supply simulation.")
        return
    st.markdown(badge(row["severity"]), unsafe_allow_html=True)
    st.metric("Overall risk index", f"{row['overall_score']:.1f} / 100")
    st.progress(row["overall_score"] / 100)
    chart = pd.DataFrame({"dimension": ["Delivery", "Inventory", "Financial", "Production"], "score": [row["delivery_score"], row["inventory_score"], row["financial_score"], row["production_score"]]}).set_index("dimension")
    st.bar_chart(chart, color="#f97316")
    st.caption(f"Formula version: {row['formula_version']}")


def suppliers(api: BottleneckApi) -> None:
    page_header("Alternative supplier comparison", "Authorized synthetic suppliers; these are not live sourcing offers.")
    incident = _selected_incident(api)
    if not incident:
        return
    rows = api.get("/suppliers", component_id=incident.get("component_id"))
    if not rows:
        empty_state("No supplier candidates", "No authorized component-qualified records were found.")
        return
    frame = pd.DataFrame(rows)
    st.dataframe(frame[["supplier_id", "supplier_name", "status", "unit_price", "lead_time_days", "available_capacity", "quality_score", "reliability_score", "on_time_delivery_rate"]], width="stretch", hide_index=True)
    st.scatter_chart(frame, x="lead_time_days", y="unit_price", size="available_capacity", color="quality_score")


def strategies(api: BottleneckApi) -> None:
    page_header("Recovery strategy comparison", "Only constraint-valid strategies are eligible for recommendation.")
    incident = _selected_incident(api)
    if not incident:
        return
    rows = api.get(f"/incidents/{incident['incident_id']}/strategies")
    if not rows:
        empty_state("No evaluated strategies", "Strategy records appear after planning, simulation, scoring, and validation.")
        return
    frame = pd.DataFrame([{**row, **row.get("strategy_data", {})} for row in rows])
    st.dataframe(frame, width="stretch", hide_index=True)


def approval(api: BottleneckApi) -> None:
    page_header("Human approval", "A human decision is mandatory; approval creates a plan but never places an order.")
    incident = _selected_incident(api)
    if not incident:
        return
    rows = api.get(f"/incidents/{incident['incident_id']}/strategies")
    if not rows:
        empty_state("Nothing ready for approval", "A validated recommendation and passing reflection are required.")
        return
    strategy_options = {f"{row['strategy_type']} · {row['strategy_id'][:8]}": row["strategy_id"] for row in rows}
    choice = st.selectbox("Strategy", list(strategy_options))
    decided_by = st.text_input("Decision maker")
    reason = st.text_area("Reason (required for rejection)")
    left, right = st.columns(2)
    if left.button("Approve", type="primary", width="stretch"):
        result = api.post(f"/incidents/{incident['incident_id']}/approve", {"strategy_id": strategy_options[choice], "decided_by": decided_by, "reason": reason or None})
        st.success(f"Approved. Execution plan: {result['execution_plan_id']}")
    if right.button("Reject", width="stretch"):
        result = api.post(f"/incidents/{incident['incident_id']}/reject", {"strategy_id": strategy_options[choice], "decided_by": decided_by, "reason": reason})
        st.warning(f"Rejected. Incident status: {result['incident_status']}")


def history(api: BottleneckApi) -> None:
    page_header("Incident history & memory", "Planned, predicted, and observed outcomes remain explicitly distinct.")
    incident = _selected_incident(api)
    if not incident:
        return
    rows = api.get(f"/incidents/{incident['incident_id']}/history")
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        empty_state("No historical memory", "Memory is written after an approved plan; observed outcomes are added separately.")


def evaluation(api: BottleneckApi) -> None:
    page_header("Agent evaluation", "Measured results only; no placeholder pass rates are displayed.")
    if st.button("Run deterministic evaluation", type="primary"):
        with st.spinner("Executing source-backed checks…"):
            api.post("/evaluations/run", {})
        st.success("Evaluation completed and persisted.")
    rows = api.get("/evaluations")
    if rows:
        latest = rows[0]
        st.caption(
            f"Latest run: {latest['status']} · {latest['scenario_count']} scenarios · "
            f"{latest['started_at']} · {latest['metrics'].get('suite_kind', 'unknown suite')}"
        )
        metrics = latest["metrics"]
        metric_rows = []
        for name, metric in metrics.items():
            if not isinstance(metric, dict) or "measured" not in metric:
                continue
            value = metric.get("value_percent")
            if value is None and "value" in metric:
                value = metric["value"]
            metric_rows.append({
                "metric": name.replace("_", " "),
                "measured": metric["measured"],
                "observed_value": value,
                "numerator": metric.get("numerator"),
                "denominator": metric.get("denominator"),
                "method": metric["method"],
                "reason": metric.get("reason"),
            })
        st.dataframe(pd.DataFrame(metric_rows), width="stretch", hide_index=True)
        st.subheader("Scenario results")
        st.dataframe(pd.DataFrame(metrics.get("scenario_results", [])), width="stretch", hide_index=True)
        with st.expander("Evaluation run history"):
            st.dataframe(
                pd.DataFrame(rows)[["evaluation_run_id", "status", "scenario_count", "started_at", "completed_at"]],
                width="stretch",
                hide_index=True,
            )
    else:
        empty_state("No evaluation runs", "Run the deterministic suite to create the first measured result.")


def settings(api: BottleneckApi) -> None:
    page_header("Settings", "Runtime endpoints and business-policy transparency.")
    st.text_input("Backend API", api.base_url, disabled=True)
    st.code("Risk weights: delivery 25% · inventory 30% · financial 20% · production 25%\nStrategy weights: cost 30% · delivery 30% · quality 20% · residual risk 20%\nMaximum automatic revisions: 2")
    st.info("Model credentials are read from environment variables and are never displayed here.")


PAGE_RENDERERS = {
    "Executive Dashboard": executive,
    "Create Incident": create_incident,
    "Active Incidents": active_incidents,
    "Incident Investigation": investigation,
    "Live Agent Workflow": workflow,
    "Evidence Explorer": evidence,
    "Risk Analysis": risk,
    "Alternative Supplier Comparison": suppliers,
    "Recovery Strategy Comparison": strategies,
    "Human Approval": approval,
    "Incident History & Memory": history,
    "Agent Evaluation": evaluation,
    "Settings": settings,
}
