"use client";

import { AlertCircle, Loader2, RefreshCw, Satellite } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/formatters";
import { useBottleneckDashboard } from "@/hooks/use-bottleneck-dashboard";
import { DashboardShell } from "./dashboard-shell";
import { EvaluationSummary } from "./evaluation-summary";
import { IncidentDetail } from "./incident-detail";
import { IncidentQueue } from "./incident-queue";
import { KpiGrid } from "./kpi-grid";
import { SupplierComparison } from "./supplier-comparison";

export function OperationsDashboard() {
  const {
    data,
    detail,
    selectedIncidentId,
    setSelectedIncidentId,
    loading,
    detailLoading,
    running,
    error,
    actionMessage,
    lastUpdated,
    refresh,
    refreshDetail,
    runSelectedInvestigation,
  } = useBottleneckDashboard();

  const selectedIncident =
    data?.incidents.find(
      (incident) => incident.incident_id === selectedIncidentId,
    ) ?? null;

  return (
    <DashboardShell>
      <header
        id="overview"
        className="sticky top-0 z-30 flex min-h-18 items-center gap-4 border-b border-border bg-background/95 px-5 py-4 pl-18 backdrop-blur lg:px-8"
      >
        <div>
          <p className="font-display text-2xl tracking-wide sm:text-3xl">
            Operations command center
          </p>
          <p className="mt-1 text-xs uppercase text-muted-foreground">
            {lastUpdated
              ? `Live API · refreshed ${formatDateTime(lastUpdated.toISOString())}`
              : "Connecting to Bottleneck API"}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="ml-auto"
          onClick={() => void refresh()}
          disabled={loading}
        >
          <RefreshCw className={loading ? "animate-spin" : ""} />
          <span className="hidden sm:inline">Refresh data</span>
        </Button>
      </header>

      <div className="space-y-6 p-4 sm:p-6 lg:p-8">
        {error && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-lg border border-destructive bg-destructive/10 p-4 text-destructive"
          >
            <AlertCircle className="mt-0.5 size-5 shrink-0" />
            <div>
              <p className="font-bold uppercase">Dashboard action needs attention</p>
              <p className="mt-1 text-sm">{error}</p>
            </div>
          </div>
        )}

        {actionMessage && (
          <div className="flex items-center gap-3 rounded-lg border border-success bg-success/10 p-4 text-success">
            <Satellite className="size-5" />
            <p className="text-sm font-bold uppercase">{actionMessage}</p>
          </div>
        )}

        {loading && !data ? (
          <div className="flex min-h-[65vh] items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            Loading live operations data…
          </div>
        ) : data ? (
          <>
            <KpiGrid summary={data.summary} />

            <section id="incidents" className="scroll-mt-24 space-y-6">
              <IncidentQueue
                incidents={data.incidents}
                selectedIncidentId={selectedIncidentId}
                onSelect={setSelectedIncidentId}
              />
              <IncidentDetail
                incident={selectedIncident}
                detail={detail}
                loading={detailLoading}
                running={running}
                onRun={() => void runSelectedInvestigation()}
                onRefresh={() => void refreshDetail()}
              />
            </section>

            <section
              id="suppliers"
              className="grid scroll-mt-24 gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(20rem,0.75fr)]"
            >
              <SupplierComparison suppliers={data.suppliers} />
              <EvaluationSummary evaluations={data.evaluations} />
            </section>

            <footer className="flex flex-col gap-2 border-t border-border pt-5 text-xs uppercase text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span>{data.summary.classification}</span>
              <span>Source: Bottleneck FastAPI + SQLite</span>
            </footer>
          </>
        ) : (
          <div className="rounded-lg border border-border bg-background p-10 text-center">
            <p className="font-display text-2xl">API unavailable</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Start the backend on port 8000, then refresh this page.
            </p>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
