import { AlertTriangle, Bot, CalendarClock, Loader2, Play, RefreshCw } from "lucide-react";
import DashboardCard from "@/components/dashboard/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatCurrency, formatDateTime, humanize } from "@/lib/formatters";
import type { Incident, IncidentDetail as IncidentDetailType } from "@/types/api";
import { StatusBadge } from "./status-badge";

interface IncidentDetailProps {
  incident: Incident | null;
  detail: IncidentDetailType | null;
  loading: boolean;
  running: boolean;
  onRun: () => void;
  onRefresh: () => void;
}

export function IncidentDetail({
  incident,
  detail,
  loading,
  running,
  onRun,
  onRefresh,
}: IncidentDetailProps) {
  if (!incident) {
    return (
      <DashboardCard title="Incident analysis">
        <p className="py-12 text-center text-sm text-muted-foreground">
          Select an incident to inspect its modeled impact and workflow.
        </p>
      </DashboardCard>
    );
  }

  const latestRun = detail?.workflow?.workflow_runs.at(-1);
  const agentRuns = detail?.workflow?.agent_runs ?? [];
  const progress = latestRun?.state.progress_percent ?? (latestRun?.status === "COMPLETED" ? 100 : 0);
  const expectedAgents = [
    "orchestrator_triage_agent",
    "supplier_intelligence_agent",
    "logistics_intelligence_agent",
    "demand_inventory_agent",
    "production_impact_agent",
    "risk_analyst_agent",
    "alternative_supplier_agent",
    "recovery_planning_agent",
    "reflection_quality_agent",
  ];
  const currentAgentRuns = agentRuns.filter(
    (agent) =>
      agent.workflow_run_id === latestRun?.workflow_run_id && !agent.tool_name,
  );
  const latestByAgent = new Map(
    currentAgentRuns.map((agent) => [agent.agent_name, agent]),
  );

  return (
    <DashboardCard
      title="Incident analysis"
      addon={<StatusBadge status={incident.status} />}
    >
      <div className="space-y-5">
        <div>
          <p className="font-display text-2xl">{incident.title}</p>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            {incident.description}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant="secondary">{incident.component_id ?? "No component"}</Badge>
            <Badge variant="secondary">{incident.supplier_id ?? "No supplier"}</Badge>
            <Badge variant="secondary">{incident.order_id ?? "No order"}</Badge>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={onRun} disabled={running || incident.status === "APPROVED"}>
            {running ? (
              <Loader2 className="animate-spin" />
            ) : (
              <Play />
            )}
            {running ? `Agents working · ${progress}%` : "Run investigation"}
          </Button>
          <Button variant="secondary" onClick={onRefresh} disabled={loading}>
            <RefreshCw className={loading ? "animate-spin" : ""} />
            Refresh
          </Button>
        </div>

        {loading ? (
          <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Loading incident evidence…
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <DetailMetric
              label="Modeled exposure"
              value={
                detail?.simulation
                  ? formatCurrency(detail.simulation.financial_exposure)
                  : "Unavailable"
              }
            />
            <DetailMetric
              label="Downtime"
              value={
                detail?.simulation
                  ? `${detail.simulation.estimated_downtime_days.toFixed(1)} days`
                  : "Unavailable"
              }
            />
            <DetailMetric
              label="First shortage"
              value={detail?.simulation?.first_actual_shortage_date ?? "No shortage"}
            />
            <DetailMetric
              label="Risk"
              value={
                detail?.risk
                  ? `${detail.risk.severity} · ${detail.risk.overall_score.toFixed(0)}/100`
                  : "Not assessed"
              }
            />
          </div>
        )}

        <div id="workflow" className="rounded-lg border border-border bg-accent p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Bot className="size-4 text-primary" />
              <p className="text-sm font-bold uppercase">Agent workflow</p>
            </div>
            {latestRun ? (
              <StatusBadge status={latestRun.status} />
            ) : (
              <Badge variant="secondary">Not started</Badge>
            )}
          </div>
          {latestRun?.status === "RUNNING" && (
            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                <span>{latestRun.state.phase_label ?? "Agents are working"}</span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-border">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                  style={{ width: `${Math.max(2, Math.min(progress, 100))}%` }}
                />
              </div>
            </div>
          )}
          {latestRun?.state.error && (
            <div className="mt-4 flex gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <span>{latestRun.state.error}</span>
            </div>
          )}
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {expectedAgents.map((agentName, index) => {
              const agent = latestByAgent.get(agentName);
              const status = agent?.status ?? (
                latestRun?.status === "COMPLETED" && agentName === "alternative_supplier_agent"
                  ? "SKIPPED"
                  : "PENDING"
              );
              return (
                <div
                  key={`${agentName}-${index}`}
                  className="flex min-w-0 items-center justify-between gap-2 rounded-md border border-border bg-background px-3 py-2 transition-colors"
                >
                  <span className="truncate text-xs uppercase">{humanize(agentName)}</span>
                  <StatusBadge status={status} />
                </div>
              );
            })}
          </div>
          {latestRun?.started_at && (
            <p className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
              <CalendarClock className="size-3" /> Started {formatDateTime(latestRun.started_at)}
            </p>
          )}
        </div>
      </div>
    </DashboardCard>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-bold">{value}</p>
    </div>
  );
}
