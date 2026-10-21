import {
  AlertTriangle,
  BadgeIndianRupee,
  CircleAlert,
  Clock3,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Bullet } from "@/components/ui/bullet";
import { formatCurrency } from "@/lib/formatters";
import type { DashboardSummary } from "@/types/api";

export function KpiGrid({ summary }: { summary: DashboardSummary }) {
  const metrics = [
    {
      label: "Active incidents",
      value: String(summary.active_incidents),
      detail: `${summary.critical_incidents} classified critical`,
      icon: CircleAlert,
    },
    {
      label: "Pending approvals",
      value: String(summary.pending_approvals),
      detail: "Human decision required",
      icon: AlertTriangle,
    },
    {
      label: "Modeled exposure",
      value: formatCurrency(summary.estimated_financial_exposure),
      detail: "Active incident baseline",
      icon: BadgeIndianRupee,
    },
    {
      label: "Estimated downtime",
      value: `${summary.estimated_downtime_days.toFixed(1)} d`,
      detail: `${summary.completed_investigations} completed investigations`,
      icon: Clock3,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <Card key={metric.label}>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2 uppercase">
              <Bullet /> {metric.label}
            </CardTitle>
            <metric.icon className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="bg-accent px-4 py-4">
            <p className="font-display text-4xl leading-none">{metric.value}</p>
            <p className="mt-2 text-xs uppercase text-muted-foreground">
              {metric.detail}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
