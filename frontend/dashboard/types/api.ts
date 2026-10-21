export type IncidentStatus =
  | "DETECTED"
  | "INVESTIGATING"
  | "WAITING_FOR_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "CLOSED"
  | "FAILED"
  | string;

export interface Incident {
  incident_id: string;
  title: string;
  description: string;
  event_type: string;
  status: IncidentStatus;
  supplier_id: string | null;
  component_id: string | null;
  order_id: string | null;
  source_event_id: string | null;
  detected_at: string;
  created_at: string;
  updated_at: string;
}

export interface DashboardSummary {
  active_incidents: number;
  critical_incidents: number;
  pending_approvals: number;
  estimated_financial_exposure: number;
  estimated_downtime_days: number;
  completed_investigations: number;
  recent_disruptions: Incident[];
  classification: string;
}

export interface Supplier {
  supplier_id: string;
  supplier_name: string;
  component_id: string;
  unit_price: number;
  lead_time_days: number;
  available_capacity: number;
  capacity_period: string;
  quality_score: number;
  reliability_score: number;
  on_time_delivery_rate: number;
  location: string;
  status: string;
  expedite_supported: boolean;
  expedite_lead_time_days: number | null;
  expedite_unit_surcharge: number | null;
}

export interface Simulation {
  component_id: string;
  start_date: string;
  end_date: string;
  first_safety_stock_breach_date: string | null;
  first_actual_shortage_date: string | null;
  total_shortage_quantity: number;
  unfulfilled_production_demand: number;
  estimated_downtime_days: number;
  financial_exposure: number;
  no_shortage_within_horizon: boolean;
  daily_projection: Array<Record<string, string | number | null>>;
}

export interface RiskAssessment {
  incident_id: string;
  delivery_score: number;
  inventory_score: number;
  financial_score: number;
  production_score: number;
  overall_score: number;
  severity: string;
  formula_version: string;
  assessed_at: string;
  [key: string]: unknown;
}

export interface WorkflowRun {
  workflow_run_id: string;
  incident_id: string;
  status: string;
  state: {
    phase?: string;
    phase_label?: string;
    progress_percent?: number;
    error?: string;
    recommended_strategy_id?: string | null;
    [key: string]: unknown;
  };
  started_at: string;
  completed_at: string | null;
  [key: string]: unknown;
}

export interface AgentRun {
  execution_id: string;
  workflow_run_id: string;
  agent_name: string;
  tool_name: string | null;
  status: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  error: string | null;
  retry_count: number;
  model_identifier: string | null;
  [key: string]: unknown;
}

export interface Workflow {
  workflow_runs: WorkflowRun[];
  agent_runs: AgentRun[];
}

export interface EvaluationMetric {
  measured?: boolean;
  value?: number;
  value_percent?: number | null;
  method?: string;
  reason?: string;
}

export interface EvaluationRun {
  evaluation_run_id: string;
  status: string;
  scenario_count: number;
  metrics: Record<string, EvaluationMetric | unknown>;
  started_at: string;
  completed_at: string | null;
}

export interface IncidentDetail {
  simulation: Simulation | null;
  risk: RiskAssessment | null;
  workflow: Workflow | null;
}

export interface DashboardData {
  summary: DashboardSummary;
  incidents: Incident[];
  suppliers: Supplier[];
  evaluations: EvaluationRun[];
}
