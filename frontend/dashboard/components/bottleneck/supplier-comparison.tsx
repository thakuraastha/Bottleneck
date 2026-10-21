"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import DashboardCard from "@/components/dashboard/card";
import { Badge } from "@/components/ui/badge";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import type { Supplier } from "@/types/api";

const chartConfig = {
  reliability: { label: "Reliability", color: "var(--chart-2)" },
  onTime: { label: "On-time delivery", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function SupplierComparison({ suppliers }: { suppliers: Supplier[] }) {
  const activeSuppliers = suppliers
    .filter((supplier) => supplier.status === "ACTIVE")
    .map((supplier) => ({
      supplier: supplier.supplier_id,
      reliability: supplier.reliability_score,
      onTime: Math.round(supplier.on_time_delivery_rate * 100),
    }));

  return (
    <DashboardCard
      title="Supplier resilience"
      addon={<Badge variant="outline-success">Active suppliers</Badge>}
    >
      {activeSuppliers.length === 0 ? (
        <div className="py-12 text-center text-sm text-muted-foreground">
          No active supplier measurements are available.
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-4 text-xs uppercase text-muted-foreground">
            <span className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-[var(--chart-2)]" />
              Reliability score
            </span>
            <span className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-[var(--chart-1)]" />
              On-time delivery
            </span>
          </div>
          <ChartContainer config={chartConfig} className="h-72 w-full">
            <BarChart accessibilityLayer data={activeSuppliers}>
              <CartesianGrid vertical={false} strokeDasharray="6 6" />
              <XAxis dataKey="supplier" tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tickLine={false} axisLine={false} unit="%" />
              <ChartTooltip
                cursor={false}
                content={<ChartTooltipContent indicator="dot" />}
              />
              <Bar
                dataKey="reliability"
                fill="var(--color-reliability)"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="onTime"
                fill="var(--color-onTime)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ChartContainer>
        </>
      )}
    </DashboardCard>
  );
}
