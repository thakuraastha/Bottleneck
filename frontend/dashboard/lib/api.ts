import type {
  DashboardData,
  DashboardSummary,
  EvaluationRun,
  Incident,
  IncidentDetail,
  RiskAssessment,
  Simulation,
  Supplier,
  Workflow,
} from "@/types/api";

const API_PREFIX = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new ApiError(
      payload?.detail ?? `Request failed with status ${response.status}`,
      response.status,
    );
  }

  return response.json() as Promise<T>;
}

export async function getDashboardData(): Promise<DashboardData> {
  const [summary, incidents, suppliers, evaluations] = await Promise.all([
    request<DashboardSummary>("/dashboard/summary"),
    request<Incident[]>("/incidents"),
    request<Supplier[]>("/suppliers"),
    request<EvaluationRun[]>("/evaluations"),
  ]);

  return { summary, incidents, suppliers, evaluations };
}

async function optionalRequest<T>(path: string): Promise<T | null> {
  try {
    return await request<T>(path);
  } catch (error) {
    if (error instanceof ApiError && [404, 422].includes(error.status)) {
      return null;
    }
    throw error;
  }
}

export async function getIncidentDetail(
  incidentId: string,
): Promise<IncidentDetail> {
  const encoded = encodeURIComponent(incidentId);
  const [simulation, risk, workflow] = await Promise.all([
    optionalRequest<Simulation>(`/incidents/${encoded}/simulation`),
    optionalRequest<RiskAssessment>(`/incidents/${encoded}/risk`),
    optionalRequest<Workflow>(`/incidents/${encoded}/workflow`),
  ]);

  return { simulation, risk, workflow };
}

export function runInvestigation(incidentId: string): Promise<WorkflowRunResult> {
  return request<WorkflowRunResult>(
    `/incidents/${encodeURIComponent(incidentId)}/run`,
    { method: "POST" },
  );
}

export interface WorkflowRunResult {
  workflow_run_id: string;
  status: string;
  [key: string]: unknown;
}
