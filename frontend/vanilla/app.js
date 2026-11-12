"use strict";

const API_BASE = window.location.port === "3000" || window.location.protocol === "file:"
  ? `http://${window.location.hostname || "127.0.0.1"}:8000`
  : window.location.origin;

const AGENTS = [
  { name: "orchestrator_triage_agent", title: "Orchestrator & triage", framework: "Google ADK", outputKey: "triage_output", copy: "Validates identifiers and scopes the disruption." },
  { name: "supplier_intelligence_agent", title: "Supplier intelligence", framework: "Google ADK", outputKey: "investigation_supplier", copy: "Retrieves supplier commitments, capacity, quality, and reliability." },
  { name: "logistics_intelligence_agent", title: "Logistics intelligence", framework: "Google ADK", outputKey: "investigation_logistics", copy: "Checks shipment state, revised ETA, and deterministic delay." },
  { name: "demand_inventory_agent", title: "Demand & inventory", framework: "Google ADK", outputKey: "investigation_inventory", copy: "Projects stock, demand, safety-stock breach, and shortage." },
  { name: "production_impact_agent", title: "Production impact", framework: "Google ADK", outputKey: "investigation_production", copy: "Connects component shortages to downtime and financial exposure." },
  { name: "adk_state_supervisor", title: "Shared-state supervisor", framework: "Google ADK", outputKey: "adk_state_supervision", copy: "Validates ADK session-state handoffs before deterministic risk processing." },
  { name: "risk_analyst_agent", title: "Risk analyst", framework: "Google ADK", outputKey: "risk_interpretation", copy: "Explains the deterministic risk score without modifying it." },
  { name: "alternative_supplier_agent", title: "Alternative supplier bridge", framework: "Google ADK + A2A", outputKey: "alternative_supplier_research", copy: "Routes authorized supplier research to the CrewAI service." },
  { name: "crewai_supplier_researcher", title: "Supplier researcher", framework: "CrewAI", outputKey: "crewai_supplier_researcher", copy: "Retrieves authorized synthetic supplier records." },
  { name: "crewai_supplier_analyst", title: "Supplier analyst", framework: "CrewAI", outputKey: "crewai_supplier_analyst", copy: "Compares capacity, cost, quality, reliability, and lead time." },
  { name: "crewai_supplier_reviewer", title: "Supplier reviewer", framework: "CrewAI", outputKey: "crewai_supplier_reviewer", copy: "Applies eligibility gates and validates the structured result." },
  { name: "recovery_planning_agent", title: "Recovery planner", framework: "Google ADK", outputKey: "recovery_proposals", copy: "Builds evidence-grounded allocation proposals." },
  { name: "reflection_quality_agent", title: "Reflection & quality", framework: "Google ADK", outputKey: "reflection_review", copy: "Checks plan quality and drives bounded revisions." },
];

const ENDPOINTS = [
  ["GET", "/health", "API health and launcher readiness"],
  ["GET", "/dashboard/summary", "Operational KPIs and modeled exposure"],
  ["GET", "/incidents", "Persisted incident queue"],
  ["POST", "/integrations/email/ingest", "Guarded email-to-incident ingestion with source evidence"],
  ["POST", "/incidents/{id}/run", "Background Google ADK + CrewAI investigation"],
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
  const localFrontend = window.location.port === "3000" || window.location.protocol === "file:";
  $("#system-state").textContent = online
    ? `${localFrontend ? "Local" : "Cloud"} service online`
    : "API unavailable";
}

const apiDocsLink = $("#api-docs-link");
if (apiDocsLink) apiDocsLink.href = `${API_BASE}/docs`;

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
  const loadDetails = async (incidentId) => {
    const encoded = encodeURIComponent(incidentId);
    return Promise.all([
      request(`/incidents/${encoded}/audit`), optional(`/incidents/${encoded}/simulation`),
    ]);
  };
  try {
    [state.audit, state.simulation] = await loadDetails(state.selectedIncidentId);
  } catch (error) {
    if (error.status !== 404) throw error;
    localStorage.removeItem("bottleneck-selected-incident");
    state.incidents = await request("/incidents");
    state.selectedIncidentId = state.incidents.find((item) => !["CLOSED", "FAILED"].includes(item.status))?.incident_id
      || state.incidents[0]?.incident_id
      || null;
    if (!state.selectedIncidentId) {
      state.audit = null;
      state.simulation = null;
      return;
    }
    localStorage.setItem("bottleneck-selected-incident", state.selectedIncidentId);
    [state.audit, state.simulation] = await loadDetails(state.selectedIncidentId);
    notice("The previous cloud session expired. Switched to the current deployed incident.", "info", 5000);
  }
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
    ["Visible agent stages", uniqueTopLevelAgents().size, "Google ADK and CrewAI"],
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
  const workflowRunId = latestWorkflow()?.workflow_run_id;
  (state.audit?.agent_runs || [])
    .filter((run) => !run.tool_name && (!workflowRunId || run.workflow_run_id === workflowRunId))
    .forEach((run) => latest.set(run.agent_name, run));
  return latest;
}

function agentOutputMarkup(output, placeholder = "Output will appear here while the workflow runs.") {
  if (output === null || output === undefined) {
    return `<div class="agent-output-empty">${escapeHTML(placeholder)}</div>`;
  }
  const text = typeof output === "string" ? output : JSON.stringify(output, null, 2);
  const summary = typeof output === "object"
    ? output.summary || output.narrative || output.rationale || output.output || output.reason
    : output;
  return `<div class="agent-output-preview">${escapeHTML(String(summary || "Structured output ready").slice(0, 220))}</div>
    <details class="agent-output"><summary>View complete output</summary><pre>${escapeHTML(text)}</pre></details>`;
}

function agentEvidenceMarkup(agent, output, outputs) {
  const supplierStage = agent.name.includes("supplier") || agent.name === "recovery_planning_agent";
  const evidenceOutput = supplierStage ? (outputs.alternative_supplier_research || output) : output;
  const serialized = JSON.stringify(evidenceOutput || {});
  const evidence = (state.audit?.evidence || []).filter((item) =>
    serialized.includes(item.evidence_id)
      || serialized.includes(item.source_record_id)
      || (agent.name === "orchestrator_triage_agent" && item.source_system === "EMAIL")
  );
  const suppliers = state.suppliers.filter((item) =>
    serialized.includes(item.supplier_id)
      || (supplierStage && (state.audit?.supplier_candidates || []).some((candidate) => candidate.supplier_id === item.supplier_id))
  );
  const sources = evidence.map((item) => `${item.source_system} · ${item.source_record_id}`);
  const supplierProof = suppliers.map((item) =>
    `${item.supplier_id} · ${item.component_id} · Q${number(item.quality_score)} · ${number(item.available_capacity)} units`
  );
  const proof = [...new Set([...sources, ...supplierProof])];
  return `<details class="agent-evidence" ${proof.length ? "" : "disabled"}>
    <summary>Evidence & provenance <span>${proof.length}</span></summary>
    ${proof.length ? `<ul>${proof.map((item) => `<li>${escapeHTML(item)}</li>`).join("")}</ul>` : `<p>No direct source references published yet.</p>`}
  </details>`;
}

function renderAgents() {
  const latest = uniqueTopLevelAgents();
  const outputs = latestWorkflow()?.state?.agent_outputs || {};
  const complete = AGENTS.filter((agent) => latest.get(agent.name)?.status === "COMPLETED").length;
  $("#agent-completion").textContent = `${complete} / ${AGENTS.length} complete`;
  $("#agent-grid").innerHTML = AGENTS.map((agent, index) => {
    const run = latest.get(agent.name);
    const output = outputs[agent.outputKey];
    const displayStatus = run?.status || (output?.skipped ? "SKIPPED" : output ? "COMPLETED" : "PENDING");
    const pendingCopy = (() => {
      if (displayStatus === "RUNNING") return "Working now. This card updates as soon as the stage publishes evidence.";
      if (agent.name === "adk_state_supervisor") return "Waiting for all four investigation agents to join. The ADK state validator normally completes in milliseconds.";
      if (agent.name === "crewai_supplier_researcher") return "Queued behind the A2A bridge. It will retrieve authorized supplier records first.";
      if (agent.name === "crewai_supplier_analyst") return "Waiting for the Researcher output, then it will compare cost, capacity, quality, and lead time.";
      if (agent.name === "crewai_supplier_reviewer") return "Waiting for Researcher and Analyst outputs, then it will apply the final eligibility gate.";
      return "Waiting for the required upstream stage.";
    })();
    return `<article class="agent-card" data-framework="${className(agent.framework)}">
      <div class="agent-card-top"><span class="agent-number">STAGE ${String(index + 1).padStart(2, "0")}</span><span class="framework-badge">${escapeHTML(agent.framework)}</span></div>
      ${statusBadge(displayStatus)}<h3>${escapeHTML(agent.title)}</h3><p>${escapeHTML(agent.copy)}</p>
      ${agentOutputMarkup(output, pendingCopy)}
      ${agentEvidenceMarkup(agent, output, outputs)}
      <div class="agent-meta"><span>${escapeHTML(run?.model_identifier || agent.framework)}</span><span>${run?.duration_ms == null ? "—" : `${number(run.duration_ms)} ms`}</span></div>
    </article>`;
  }).join("");
  const workflowRunId = latestWorkflow()?.workflow_run_id;
  const runs = (state.audit?.agent_runs || [])
    .filter((run) => !workflowRunId || run.workflow_run_id === workflowRunId)
    .slice().reverse().slice(0, 60);
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
    const runRequest = request(`/incidents/${encodeURIComponent(state.selectedIncidentId)}/run`, { method: "POST" });
    let result = null;
    for (let attempt = 0; attempt < 240; attempt += 1) {
      await loadSelectedIncident();
      renderAll();
      const workflow = result
        ? state.audit?.workflow_runs?.find((item) => item.workflow_run_id === result.workflow_run_id)
        : latestWorkflow();
      if (workflow && workflow.status !== "RUNNING") {
        result = await runRequest;
        await loadAll({ quiet: true });
        if (workflow.status === "COMPLETED") notice("All workflow stages completed and the audit trail is ready.", "success", 8000);
        else throw new Error(workflow.state?.error || "The investigation failed.");
        return;
      }
      if (!result) {
        const settled = await Promise.race([
          runRequest.then((value) => ({ value })),
          new Promise((resolve) => window.setTimeout(() => resolve(null), 50)),
        ]);
        if (settled) result = settled.value;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
    }
    throw new Error("The workflow is still running. Refresh to continue following it.");
  } catch (error) { notice(error.message, "error", 0); }
  finally { state.running = false; renderIncidents(); }
}

async function ingestEmail() {
  const button = $("#ingest-email");
  const resultNode = $("#email-ingestion-result");
  const payload = {
    message_id: $("#email-message-id").value.trim(),
    sender: $("#email-sender").value.trim(),
    subject: $("#email-subject").value.trim(),
    body: $("#email-body").value.trim(),
    received_at: new Date().toISOString(),
  };
  button.disabled = true;
  resultNode.textContent = "Validating supplier and order references…";
  try {
    const result = await request("/integrations/email/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await loadAll({ quiet: true });
    await selectIncident(result.incident_id, true);
    resultNode.textContent = `${humanize(result.event_type)} · ${result.supplier_id || "supplier inferred later"} · evidence saved`;
    notice("Email converted to an incident with verified source evidence.", "success", 8000);
  } catch (error) {
    resultNode.textContent = error.message;
    notice(error.message, "error", 0);
  } finally { button.disabled = false; }
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
$("#ingest-email").addEventListener("click", () => void ingestEmail());
$("#approve-button").addEventListener("click", () => void recordDecision("approve"));
$("#reject-button").addEventListener("click", () => void recordDecision("reject"));
$("#run-evaluation").addEventListener("click", () => void runEvaluation());
window.addEventListener("hashchange", () => selectTab(location.hash.slice(1) || "overview", false));

selectTab(location.hash.slice(1) || "overview", false);
void loadAll({ quiet: true });
