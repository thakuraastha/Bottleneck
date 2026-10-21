import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import DashboardCard from "@/components/dashboard/card";
import { formatDateTime, humanize } from "@/lib/formatters";
import type { Incident } from "@/types/api";
import { StatusBadge } from "./status-badge";

interface IncidentQueueProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  onSelect: (incidentId: string) => void;
}

export function IncidentQueue({
  incidents,
  selectedIncidentId,
  onSelect,
}: IncidentQueueProps) {
  return (
    <DashboardCard
      title="Incident queue"
      addon={<Badge variant="outline">{incidents.length} records</Badge>}
    >
      {incidents.length === 0 ? (
        <div className="py-12 text-center text-sm text-muted-foreground">
          No incidents have been recorded.
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Incident</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Component</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead className="text-right">Inspect</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {incidents.map((incident) => (
              <TableRow
                key={incident.incident_id}
                data-state={
                  selectedIncidentId === incident.incident_id
                    ? "selected"
                    : undefined
                }
              >
                <TableCell className="min-w-60 whitespace-normal">
                  <p className="font-medium">{incident.title}</p>
                  <p className="mt-1 text-xs uppercase text-muted-foreground">
                    {humanize(incident.event_type)}
                  </p>
                </TableCell>
                <TableCell>
                  <StatusBadge status={incident.status} />
                </TableCell>
                <TableCell>{incident.component_id ?? "Not linked"}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatDateTime(incident.updated_at)}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant={
                      selectedIncidentId === incident.incident_id
                        ? "default"
                        : "secondary"
                    }
                    size="sm"
                    onClick={() => onSelect(incident.incident_id)}
                  >
                    {selectedIncidentId === incident.incident_id
                      ? "Selected"
                      : "View"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </DashboardCard>
  );
}
