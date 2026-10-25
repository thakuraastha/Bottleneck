"use strict";

const API_BASE = window.location.port === "3000" || window.location.protocol === "file:"
  ? `http://${window.location.hostname || "127.0.0.1"}:8000`
  : window.location.origin;

const AGENTS = [
  ["orchestrator_triage_agent", "Orchestrator & triage", "Validates identifiers and scopes the disruption."],
  ["supplier_intelligence_agent", "Supplier intelligence", "Retrieves supplier commitments, capacity, quality, and reliability."],
  ["logistics_intelligence_agent", "Logistics intelligence", "Checks shipment state, revised ETA, and deterministic delay."],
  ["demand_inventory_agent", "Demand & inventory", "Projects stock, demand, safety-stock breach, and shortage."],
  ["production_impact_agent", "Production impact", "Connects component shortages to downtime and financial exposure."],
  ["risk_analyst_agent", "Risk analyst", "Explains the deterministic risk score without modifying it."],
  ["alternative_supplier_agent", "Alternative supplier", "Runs supplier research when routing rules require it."],
  ["recovery_planning_agent", "Recovery planner", "Builds evidence-grounded allocation proposals."],
  ["reflection_quality_agent", "Reflection & quality", "Checks plan quality and drives bounded revisions."],
];

const ENDPOINTS = [
  ["GET", "/health", "API health and launcher readiness"],
  ["GET", "/dashboard/summary", "Operational KPIs and modeled exposure"],
  ["GET", "/incidents", "Persisted incident queue"],
  ["POST", "/incidents/{id}/run", "Background nine-stage investigation"],
  ["GET", "/incidents/{id}/audit", "Complete evidence and reasoning trail"],
  ["GET", "/incidents/{id}/simulation", "Deterministic daily supply projection"],
  ["POST", "/incidents/{id}/approve", "Human approval and local execution plan"],
  ["POST", "/incidents/{id}/reject", "Human rejection with recorded reason"],
  ["GET", "/suppliers", "Authorized synthetic supplier records"],
  ["GET", "/evaluations", "Stored quality evaluation runs"],
  ["POST", "/evaluations/run", "Execute deterministic evaluation suite"],
  ["GET", "/system/compliance", "Live evidence for all 11 project criteria"],
  ["GET", "/a2a/.well-known/agent-card.json", "CrewAI A2A agent capability card"],
];

const state = {
  summary: null,
  incidents: [],
  suppliers: [],
  evaluations: [],
  compliance: null,
  selectedIncidentId: null,
  audit: null,
  simulation: null,
  loading: false,
  running: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function className(value) {
  return String(value || "neutral").toLowerCase().replaceAll("_", "-").replaceAll(" ", "-");
}

function humanize(value) {
  return String(value || "—").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function money(value) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(value || 0));
}

function number(value, digits = 0) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(Number(value || 0));
}

function dateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? escapeHTML(value)
    : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function safeValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return escapeHTML(JSON.stringify(value));
  return escapeHTML(value);
}

function statusBadge(value) {
  return `<span class="status ${className(value)}">${escapeHTML(humanize(value))}</span>`;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(payload?.detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function optional(path) {
  try { return await request(path); }
  catch (error) {
    if ([404, 422].includes(error.status)) return null;
    throw error;
  }
}

function notice(message, type = "info", timeout = 6500) {
  if (type === "error") clearNotices("error");
  const item = document.createElement("div");
  item.className = `notice ${type}`;
  item.innerHTML = `<strong>${type === "error" ? "Needs attention" : type === "success" ? "Complete" : "Update"}</strong><span>${escapeHTML(message)}</span>`;
  $("#notice-stack").prepend(item);
  if (timeout) window.setTimeout(() => item.remove(), timeout);
}

function clearNotices(type) {
  $$(`#notice-stack .notice${type ? `.${type}` : ""}`).forEach((item) => item.remove());
}

function setApiOnline(online) {
  $("#api-status").classList.toggle("is-online", online);
  $("#api-status").innerHTML = `<span></span>${online ? "Live API" : "API offline"}`;
  $("#system-state").textContent = online ? "Local system online" : "API unavailable";
}

function selectTab(name, updateHash = true) {
  const valid = $(`[data-panel="${name}"]`) ? name : "overview";
  $$("[data-panel]").forEach((panel) => panel.classList.toggle("is-active", panel.dataset.panel === valid));
  $$("[data-tab]").forEach((button) => button.classList.toggle("is-active", button.dataset.tab === valid));
  const labels = {
    overview: "Operations overview", incidents: "Incident command", evidence: "Evidence & impact",
    agents: "Agent workflow", strategies: "Recovery & approval", suppliers: "Supplier network", evaluation: "Evaluation evidence",
  };
  $("#page-title").textContent = labels[valid];
  if (updateHash) history.replaceState(null, "", `#${valid}`);
  closeMenu();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function closeMenu() {
  $("#sidebar").classList.remove("is-open");
  $("#sidebar-scrim").classList.remove("is-open");
}

async function loadAll({ quiet = false } = {}) {
  if (state.loading) return;
  state.loading = true;
  $("#refresh-button").disabled = true;
  try {
    const [summary, incidents, suppliers, evaluations, compliance] = await Promise.all([
      request("/dashboard/summary"), request("/incidents"), request("/suppliers"), request("/evaluations"), request("/system/compliance"),
    ]);
    state.summary = summary;
    state.incidents = incidents;
    state.suppliers = suppliers;
    state.evaluations = evaluations;
    state.compliance = compliance;
    const remembered = localStorage.getItem("bottleneck-selected-incident");
    const preferred = incidents.find((item) => item.incident_id === state.selectedIncidentId)
      || incidents.find((item) => item.incident_id === remembered)
      || incidents.find((item) => !["CLOSED", "FAILED"].includes(item.status))
      || incidents[0];
    state.selectedIncidentId = preferred?.incident_id || null;
    if (state.selectedIncidentId) localStorage.setItem("bottleneck-selected-incident", state.selectedIncidentId);
    setApiOnline(true);
    clearNotices("error");
    await loadSelectedIncident();
    renderAll();
    $("#last-refreshed").textContent = dateTime(new Date().toISOString());
    if (!quiet) notice("Dashboard refreshed from FastAPI and SQLite.", "success", 2500);
  } catch (error) {
    setApiOnline(false);
    notice(error.message, "error", 0);
    renderOffline();
  } finally {
    state.loading = false;
    $("#refresh-button").disabled = false;
  }
}

async function loadSelectedIncident() {
  if (!state.selectedIncidentId) {
    state.audit = null;
    state.simulation = null;
    return;
  }
  const encoded = encodeURIComponent(state.selectedIncidentId);
  [state.audit, state.simulation] = await Promise.all([
    request(`/incidents/${encoded}/audit`), optional(`/incidents/${encoded}/simulation`),
  ]);
}

function selectedIncident() {
  return state.incidents.find((item) => item.incident_id === state.selectedIncidentId) || state.audit?.incident || null;
}

function latestWorkflow() { return state.audit?.workflow_runs?.at(-1) || null; }
function latestRisk() { return state.audit?.risk_assessments?.at(-1) || null; }
function latestReflection() { return state.audit?.reflections?.at(-1) || null; }

function renderAll() {
  renderMetrics();
  renderOverviewIncidents();
  renderReadiness();
  renderCapabilities();
  renderIncidents();
  renderProgress();
  renderEvidence();
  renderAgents();
  renderStrategies();
  renderSuppliers();
  renderEvaluations();
  renderCompliance();
  renderEndpoints();
}

function renderOffline() {
  $("#metric-grid").innerHTML = `<div class="card empty-state">Start the FastAPI service on port 8000, then refresh.</div>`;
}

function renderMetrics() {
  const summary = state.summary || {};
  const metrics = [
    ["Active incidents", summary.active_incidents, "Open operational records", "AI"],
    ["Pending approvals", summary.pending_approvals, "Human decision required", "HA"],
    ["Modeled exposure", money(summary.estimated_financial_exposure), "Synthetic scenario estimate", "₹"],
    ["Estimated downtime", `${number(summary.estimated_downtime_days, 1)} d`, `${summary.completed_investigations || 0} completed investigations`, "DT"],
  ];
  $("#metric-grid").innerHTML = metrics.map(([label, value, note, icon]) => `
    <article class="metric-card"><div class="metric-top"><span class="metric-label">${escapeHTML(label)}</span><span class="metric-icon">${escapeHTML(icon)}</span></div><div class="metric-value">${escapeHTML(value)}</div><div class="metric-note">${escapeHTML(note)}</div></article>
  `).join("");
}

function renderOverviewIncidents() {
  $("#overview-incidents").classList.remove("skeleton-block");
  $("#overview-incidents").innerHTML = state.incidents.slice(0, 5).map((incident) => `
    <button class="list-row" data-incident-id="${escapeHTML(incident.incident_id)}" data-go-tab="incidents">
      <span class="row-dot"></span><span class="row-main"><strong>${escapeHTML(incident.title)}</strong><span>${escapeHTML(incident.component_id || "No component")} · ${dateTime(incident.updated_at)}</span></span>${statusBadge(incident.status)}
    </button>`).join("") || `<div class="empty-state">No incidents are stored.</div>`;
}

function renderReadiness() {
  const audit = state.audit || {};
  const checks = [
    ["Evidence records", audit.evidence?.length || 0], ["Agent events", audit.agent_runs?.length || 0],
    ["Risk assessments", audit.risk_assessments?.length || 0], ["Strategies scored", audit.strategy_evaluations?.length || 0],
    ["Reflections", audit.reflections?.length || 0], ["Human decisions", audit.human_decisions?.length || 0],
  ];
  $("#readiness-panel").innerHTML = checks.map(([label, value]) => `<div class="readiness-item"><span>${escapeHTML(label)}</span><strong>${escapeHTML(value)}</strong></div>`).join("");
}

function renderCapabilities() {
  const audit = state.audit || {};
  const capabilities = [
    ["Incident ingestion", state.incidents.length, "Events become persisted incidents"],
    ["Deterministic simulation", state.simulation ? 1 : 0, "Daily stock and shortage projection"],
    ["Evidence aggregation", audit.evidence?.length || 0, "Source-linked verified facts"],
    ["Risk scoring", audit.risk_assessments?.length || 0, "Delivery, inventory, finance, production"],
    ["Nine agent stages", uniqueTopLevelAgents().size, "Triage through quality reflection"],
    ["Supplier research", audit.supplier_candidates?.length || 0, "Eligibility and rejection reasons"],
    ["Strategy validation", audit.strategy_evaluations?.length || 0, "Constraints and weighted scoring"],
    ["Human approval", audit.human_decisions?.length || 0, "Audited approve/reject decision"],
  ];
  $("#capability-grid").innerHTML = capabilities.map(([title, count, copy]) => `<div class="capability"><strong>${escapeHTML(title)}</strong><span>${escapeHTML(copy)} · ${escapeHTML(count)} record${count === 1 ? "" : "s"}</span></div>`).join("");
}

function renderIncidents() {
  $("#incident-count").textContent = `${state.incidents.length} records`;
  $("#incident-list").innerHTML = state.incidents.map((incident) => `
    <button class="incident-row ${incident.incident_id === state.selectedIncidentId ? "is-selected" : ""}" data-incident-id="${escapeHTML(incident.incident_id)}">
      <span class="row-dot"></span><span class="row-main"><strong>${escapeHTML(incident.title)}</strong><span>${escapeHTML(incident.event_type)} · ${escapeHTML(incident.component_id || "No component")}</span></span>${statusBadge(incident.status)}
    </button>`).join("") || `<div class="empty-state">No incident records.</div>`;

  const incident = selectedIncident();
  const risk = latestRisk();
  $("#incident-detail").innerHTML = incident ? `
    <div class="card-header"><div><p class="eyebrow">${escapeHTML(incident.event_type)}</p><h2 class="detail-title">${escapeHTML(incident.title)}</h2></div>${statusBadge(incident.status)}</div>
    <p class="detail-copy">${escapeHTML(incident.description)}</p>
    <div class="chip-row"><span class="chip">${escapeHTML(incident.component_id || "No component")}</span><span class="chip">${escapeHTML(incident.supplier_id || "No supplier")}</span><span class="chip">${escapeHTML(incident.order_id || "No order")}</span></div>
    <div class="detail-metrics">
      <div class="mini-metric"><span>Modeled exposure</span><strong>${state.simulation ? money(state.simulation.financial_exposure) : "—"}</strong></div>
      <div class="mini-metric"><span>Downtime</span><strong>${state.simulation ? `${number(state.simulation.estimated_downtime_days, 1)} days` : "—"}</strong></div>
      <div class="mini-metric"><span>First shortage</span><strong>${escapeHTML(state.simulation?.first_actual_shortage_date || "None")}</strong></div>
      <div class="mini-metric"><span>Risk</span><strong>${risk ? `${escapeHTML(risk.severity)} · ${number(risk.overall_score)}/100` : "Not assessed"}</strong></div>
    </div>` : `<div class="empty-state">Select an incident.</div>`;
  $("#run-investigation").disabled = !incident || state.running;
  $("#run-investigation").textContent = state.running ? "Agents working…" : "Run investigation";
}

function renderProgress() {
  const workflow = latestWorkflow();
  const progress = workflow?.state?.progress_percent ?? (workflow?.status === "COMPLETED" ? 100 : 0);
  $("#workflow-phase").textContent = workflow?.state?.phase_label || "Not started";
  $("#workflow-status").outerHTML = statusBadge(workflow?.status || "Idle").replace("<span", `<span id="workflow-status"`);
  $("#workflow-progress").style.width = `${Math.max(0, Math.min(100, progress))}%`;
  $("#progress-percent").textContent = `${progress}%`;
  $("#progress-copy").textContent = workflow?.state?.error || (workflow ? `Run ${workflow.workflow_run_id.slice(0, 8)} · ${humanize(workflow.state?.phase || workflow.status)}` : "Choose an incident and start the investigation.");
}

function renderEvidence() {
  const evidence = state.audit?.evidence || [];
  const risk = latestRisk();
  const simulation = state.simulation;
  $("#evidence-count").textContent = `${evidence.length} evidence items`;
  $("#risk-card").innerHTML = risk ? `
    <div class="card-header"><div><p class="eyebrow">Deterministic formula</p><h3>Risk assessment</h3></div>${statusBadge(risk.severity)}</div>
    <div class="risk-score"><strong>${number(risk.overall_score, 1)}</strong><span>/ 100 overall</span></div>
    <div class="score-bars">${[["Delivery", risk.delivery_score], ["Inventory", risk.inventory_score], ["Financial", risk.financial_score], ["Production", risk.production_score]].map(([label, value]) => `<div class="score-row"><span>${label}</span><div class="score-bar"><i style="width:${Math.min(100, value)}%"></i></div><strong>${number(value)}</strong></div>`).join("")}</div>
    <p class="muted">Formula ${escapeHTML(risk.formula_version)} · assessed ${dateTime(risk.assessed_at)}</p>`
    : `<div class="empty-state">Run an investigation to create a risk assessment.</div>`;
  $("#simulation-card").innerHTML = simulation ? `
    <div class="card-header"><div><p class="eyebrow">Python supply simulator</p><h3>Impact projection</h3></div><span class="soft-badge">${simulation.daily_projection?.length || 0} days</span></div>
    <div class="simulation-summary">
      <div class="mini-metric"><span>Available horizon</span><strong>${escapeHTML(simulation.start_date)} → ${escapeHTML(simulation.end_date)}</strong></div>
      <div class="mini-metric"><span>Total shortage</span><strong>${number(simulation.total_shortage_quantity)} units</strong></div>
      <div class="mini-metric"><span>Safety breach</span><strong>${escapeHTML(simulation.first_safety_stock_breach_date || "None")}</strong></div>
      <div class="mini-metric"><span>Exposure</span><strong>${money(simulation.financial_exposure)}</strong></div>
    </div><p class="muted">These are modeled estimates calculated from inventory, dated demand, inbound shipments, and production requirements.</p>`
    : `<div class="empty-state">Simulation is unavailable for this incident.</div>`;
  $("#evidence-table").innerHTML = evidence.slice().reverse().map((item) => `
    <tr><td>${statusBadge(item.evidence_type)}</td><td><strong>${escapeHTML(item.field)}</strong></td><td>${safeValue(item.value)}${item.unit ? ` <small>${escapeHTML(item.unit)}</small>` : ""}</td><td><code>${escapeHTML(item.source_system)} / ${escapeHTML(item.source_record_id)}</code></td><td>${dateTime(item.observed_at)}</td></tr>`).join("") || `<tr><td colspan="5"><div class="empty-state">No aggregated evidence yet.</div></td></tr>`;
}

function uniqueTopLevelAgents() {
  const latest = new Map();
  (state.audit?.agent_runs || []).filter((run) => !run.tool_name).forEach((run) => latest.set(run.agent_name, run));
  return latest;
}

function renderAgents() {
  const latest = uniqueTopLevelAgents();
  const complete = AGENTS.filter(([name]) => latest.get(name)?.status === "COMPLETED").length;
  $("#agent-completion").textContent = `${complete} / ${AGENTS.length} complete`;
  $("#agent-grid").innerHTML = AGENTS.map(([name, title, copy], index) => {
    const run = latest.get(name);
    return `<article class="agent-card"><span class="agent-number">STAGE ${String(index + 1).padStart(2, "0")}</span>${statusBadge(run?.status || "PENDING")}<h3>${escapeHTML(title)}</h3><p>${escapeHTML(copy)}</p><div class="agent-meta"><span>${escapeHTML(run?.model_identifier || "Awaiting run")}</span><span>${run?.duration_ms == null ? "—" : `${number(run.duration_ms)} ms`}</span></div></article>`;
  }).join("");
  const runs = (state.audit?.agent_runs || []).slice().reverse().slice(0, 40);
  $("#agent-log").innerHTML = runs.map((run) => `<div class="timeline-item"><strong>${escapeHTML(humanize(run.agent_name))}</strong><span>${run.tool_name ? `Tool · ${escapeHTML(run.tool_name)}` : escapeHTML(run.model_identifier || "Agent stage")}</span><small>${statusBadge(run.status)} · ${dateTime(run.start_time)}</small></div>`).join("") || `<div class="empty-state">No agent events yet.</div>`;
}

function renderStrategies() {
  const strategies = state.audit?.strategies || [];
  const evaluations = new Map((state.audit?.strategy_evaluations || []).map((row) => [row.strategy_id, row]));
  const latestRun = latestWorkflow();
  const recommendedId = latestRun?.state?.recommended_strategy_id;
  $("#strategy-grid").innerHTML = strategies.map((row) => {
    const strategy = row.strategy_data || {};
    const evaluation = evaluations.get(row.strategy_id);
    const allocations = strategy.supplier_allocations || [];
    return `<article class="strategy-card ${row.strategy_id === recommendedId ? "is-recommended" : ""}">
      <div class="strategy-title"><div><p class="eyebrow">Revision ${row.revision_number}</p><h3>${escapeHTML(humanize(row.strategy_type))}</h3></div>${row.strategy_id === recommendedId ? '<span class="soft-badge">Recommended</span>' : statusBadge(evaluation?.valid ? "PASS" : "FAIL")}</div>
      <div class="strategy-score">${evaluation ? number(evaluation.weighted_score) : "—"}</div>
      <div class="allocation-list">${allocations.map((item) => `<div class="allocation"><span>${escapeHTML(item.supplier_id)}</span><strong>${number(item.quantity)} units · ${escapeHTML(item.expected_arrival_date)}</strong></div>`).join("") || '<div class="allocation"><span>No supplier allocation</span><strong>Wait strategy</strong></div>'}</div>
      <div class="detail-metrics"><div class="mini-metric"><span>Added cost</span><strong>${money(strategy.estimated_additional_cost)}</strong></div><div class="mini-metric"><span>Residual risk</span><strong>${number(strategy.residual_risk, 1)}%</strong></div></div>
    </article>`;
  }).join("") || `<div class="empty-state">No recovery strategies have been evaluated.</div>`;

  const reflection = latestReflection();
  $("#reflection-card").innerHTML = `<div class="card-header"><div><p class="eyebrow">Quality gate</p><h3>Reflection review</h3></div>${statusBadge(reflection ? (reflection.passed ? "PASS" : "FAIL") : "PENDING")}</div>${reflection ? `<div class="reflection-result ${reflection.passed ? "" : "fail"}"><strong>${reflection.passed ? "Recommendation supported" : "Revision required"}</strong><p>${escapeHTML((reflection.result_data?.issues || []).join(" · ") || "Evidence, constraints, and reasoning are consistent.")}</p></div><p class="muted">Revision ${reflection.revision_number} · ${dateTime(reflection.created_at)}</p>` : '<div class="empty-state">Reflection has not run.</div>'}`;
  const incident = selectedIncident();
  $("#decision-state").outerHTML = statusBadge(incident?.status || "No decision").replace("<span", `<span id="decision-state"`);
  const decisions = state.audit?.human_decisions || [];
  const canDecide = Boolean(recommendedId && ["WAITING_FOR_APPROVAL", "REJECTED", "APPROVED"].includes(incident?.status));
  $("#approve-button").disabled = !canDecide;
  $("#reject-button").disabled = !canDecide;
  $("#approve-button").textContent = incident?.status === "APPROVED" ? "Re-approve strategy" : "Approve strategy";
}

function renderSuppliers() {
  $("#supplier-count").textContent = `${state.suppliers.length} suppliers`;
  $("#supplier-grid").innerHTML = state.suppliers.map((supplier) => `<article class="supplier-card">
    <div class="card-header"><div><p class="eyebrow">${escapeHTML(supplier.supplier_id)}</p><h3>${escapeHTML(supplier.supplier_name)}</h3></div>${statusBadge(supplier.status)}</div>
    <p class="supplier-location">${escapeHTML(supplier.location)} · ${escapeHTML(supplier.component_id)}</p>
    <div class="supplier-stats"><div class="supplier-stat"><span>Reliability</span><strong>${number(supplier.reliability_score)} / 100</strong></div><div class="supplier-stat"><span>Quality</span><strong>${number(supplier.quality_score)} / 100</strong></div><div class="supplier-stat"><span>Capacity</span><strong>${number(supplier.available_capacity)}</strong></div><div class="supplier-stat"><span>Lead time</span><strong>${number(supplier.lead_time_days)} days</strong></div><div class="supplier-stat"><span>Unit price</span><strong>${money(supplier.unit_price)}</strong></div><div class="supplier-stat"><span>On time</span><strong>${number(supplier.on_time_delivery_rate * 100)}%</strong></div></div>
  </article>`).join("") || `<div class="empty-state">No supplier records.</div>`;
}

function renderEvaluations() {
  const latest = state.evaluations[0];
  const featured = ["workflow_completion_rate", "correct_tool_invocation_rate", "evidence_grounding_rate", "structured_output_validity_rate"];
  $("#evaluation-grid").innerHTML = latest ? featured.map((key) => {
    const metric = latest.metrics?.[key] || {};
    return `<article class="evaluation-card"><span>${escapeHTML(humanize(key))}</span><strong>${metric.value_percent == null ? "Not measured" : `${number(metric.value_percent)}%`}</strong><span>${escapeHTML(metric.method || metric.reason || "Stored deterministic measurement")}</span></article>`;
  }).join("") : `<div class="empty-state">Run the evaluation suite to create measured results.</div>`;
}

function renderCompliance() {
  const compliance = state.compliance;
  $("#compliance-summary").textContent = compliance
    ? `${compliance.passed} / ${compliance.total} passed`
    : "Checking requirements";
  $("#compliance-grid").innerHTML = (compliance?.criteria || []).map((item) => `
    <article class="compliance-card">
      <div class="compliance-title"><span>CRITERION ${number(item.criterion)}</span>${statusBadge(item.status)}</div>
      <h3>${escapeHTML(item.title)}</h3>
      <p>${escapeHTML(item.implementation)}</p>
      <ul>${item.evidence.map((evidence) => `<li>${escapeHTML(evidence)}</li>`).join("")}</ul>
    </article>`).join("") || `<div class="empty-state">Compliance evidence is unavailable.</div>`;
}

function renderEndpoints() {
  $("#endpoint-list").innerHTML = ENDPOINTS.map(([method, path, copy]) => `<div class="endpoint-item"><strong class="method">${method}</strong><code>${escapeHTML(path)}</code><span>${escapeHTML(copy)}</span><span class="status active">Connected</span></div>`).join("");
}

async function selectIncident(incidentId, goToIncidents = false) {
  state.selectedIncidentId = incidentId;
  localStorage.setItem("bottleneck-selected-incident", incidentId);
  try {
    await loadSelectedIncident();
    renderAll();
    if (goToIncidents) selectTab("incidents");
  } catch (error) { notice(error.message, "error", 0); }
}

async function runInvestigation() {
  if (!state.selectedIncidentId || state.running) return;
  state.running = true;
  renderIncidents();
  notice("Investigation accepted. The dashboard will follow every stage live.");
  try {
    const result = await request(`/incidents/${encodeURIComponent(state.selectedIncidentId)}/run`, { method: "POST" });
    for (let attempt = 0; attempt < 240; attempt += 1) {
      await loadSelectedIncident();
      renderAll();
      const workflow = state.audit?.workflow_runs?.find((item) => item.workflow_run_id === result.workflow_run_id);
      if (workflow && workflow.status !== "RUNNING") {
        await loadAll({ quiet: true });
        if (workflow.status === "COMPLETED") notice("All workflow stages completed and the audit trail is ready.", "success", 8000);
        else throw new Error(workflow.state?.error || "The investigation failed.");
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
    }
    throw new Error("The workflow is still running. Refresh to continue following it.");
  } catch (error) { notice(error.message, "error", 0); }
  finally { state.running = false; renderIncidents(); }
}

function recommendedStrategyId() {
  const fromWorkflow = latestWorkflow()?.state?.recommended_strategy_id;
  if (fromWorkflow) return fromWorkflow;
  const best = (state.audit?.strategy_evaluations || []).filter((item) => item.valid).sort((a, b) => b.weighted_score - a.weighted_score)[0];
  return best?.strategy_id || null;
}

async function recordDecision(decision) {
  const strategyId = recommendedStrategyId();
  const owner = $("#decision-owner").value.trim();
  const reason = $("#decision-reason").value.trim();
  if (!strategyId) return notice("No valid recommended strategy is available.", "error");
  if (!owner) return notice("Enter the decision owner.", "error");
  if (decision === "reject" && !reason) return notice("A rejection reason is required.", "error");
  const button = decision === "approve" ? $("#approve-button") : $("#reject-button");
  button.disabled = true;
  try {
    const result = await request(`/incidents/${encodeURIComponent(state.selectedIncidentId)}/${decision}`, {
      method: "POST",
      body: JSON.stringify({ strategy_id: strategyId, decided_by: owner, reason: reason || null }),
    });
    await loadAll({ quiet: true });
    notice(`${humanize(decision)} recorded. Incident status is ${humanize(result.incident_status)}.`, "success", 8000);
  } catch (error) { notice(error.message, "error", 0); }
  finally { renderStrategies(); }
}

async function runEvaluation() {
  const button = $("#run-evaluation");
  button.disabled = true;
  button.textContent = "Running suite…";
  try {
    await request("/evaluations/run", { method: "POST" });
    state.evaluations = await request("/evaluations");
    state.compliance = await request("/system/compliance");
    renderEvaluations();
    renderCompliance();
    notice("Deterministic evaluation suite completed.", "success");
  } catch (error) { notice(error.message, "error", 0); }
  finally { button.disabled = false; button.textContent = "Run evaluation suite"; }
}

document.addEventListener("click", (event) => {
  const tabButton = event.target.closest("[data-tab]");
  if (tabButton) selectTab(tabButton.dataset.tab);
  const incidentButton = event.target.closest("[data-incident-id]");
  if (incidentButton) void selectIncident(incidentButton.dataset.incidentId, Boolean(incidentButton.dataset.goTab));
});

$("#menu-button").addEventListener("click", () => {
  $("#sidebar").classList.toggle("is-open");
  $("#sidebar-scrim").classList.toggle("is-open");
});
$("#sidebar-scrim").addEventListener("click", closeMenu);
$("#refresh-button").addEventListener("click", () => void loadAll());
$("#run-investigation").addEventListener("click", () => void runInvestigation());
$("#approve-button").addEventListener("click", () => void recordDecision("approve"));
$("#reject-button").addEventListener("click", () => void recordDecision("reject"));
$("#run-evaluation").addEventListener("click", () => void runEvaluation());
window.addEventListener("hashchange", () => selectTab(location.hash.slice(1) || "overview", false));

selectTab(location.hash.slice(1) || "overview", false);
void loadAll({ quiet: true });
