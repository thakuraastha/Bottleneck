import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/formatters";

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toUpperCase();
  const variant =
    normalized === "FAILED" || normalized === "CRITICAL"
      ? "outline-destructive"
      : normalized.includes("WAITING") || normalized === "HIGH"
        ? "outline-warning"
        : normalized === "COMPLETED" || normalized === "APPROVED"
          ? "outline-success"
          : "outline";

  return <Badge variant={variant}>{humanize(status)}</Badge>;
}
