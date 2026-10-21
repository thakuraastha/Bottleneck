import { CheckCircle2, FlaskConical } from "lucide-react";
import DashboardCard from "@/components/dashboard/card";
import { Badge } from "@/components/ui/badge";
import { formatDateTime, humanize } from "@/lib/formatters";
import type { EvaluationMetric, EvaluationRun } from "@/types/api";

const featuredMetrics = [
  "workflow_completion_rate",
  "correct_tool_invocation_rate",
  "evidence_grounding_rate",
  "structured_output_validity_rate",
];

export function EvaluationSummary({ evaluations }: { evaluations: EvaluationRun[] }) {
  const latest = evaluations[0];

  return (
    <DashboardCard
      title="Evaluation evidence"
      addon={<Badge variant="outline-success">Deterministic suite</Badge>}
    >
      {!latest ? (
        <p className="py-12 text-center text-sm text-muted-foreground">
          No evaluation run is available.
        </p>
      ) : (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-lg bg-accent p-3">
            <FlaskConical className="mt-0.5 size-5 text-primary" />
            <div>
              <p className="font-bold uppercase">{latest.scenario_count} scenarios</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Completed {formatDateTime(latest.completed_at)}
              </p>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {featuredMetrics.map((key) => {
              const metric = latest.metrics[key] as EvaluationMetric | undefined;
              return (
                <div key={key} className="rounded-md border border-border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs uppercase text-muted-foreground">
                      {humanize(key)}
                    </span>
                    {metric?.measured && <CheckCircle2 className="size-4 text-success" />}
                  </div>
                  <p className="mt-2 font-display text-2xl">
                    {metric?.value_percent == null
                      ? "Not measured"
                      : `${metric.value_percent.toFixed(0)}%`}
                  </p>
                </div>
              );
            })}
          </div>
          <p className="text-xs leading-5 text-muted-foreground">
            These values come from the latest stored offline evaluation run; model-dependent metrics remain explicitly unmeasured.
          </p>
        </div>
      )}
    </DashboardCard>
  );
}
