"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getDashboardData,
  getIncidentDetail,
  runInvestigation,
} from "@/lib/api";
import type { DashboardData, IncidentDetail } from "@/types/api";

export function useBottleneckDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(
    null,
  );
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextData = await getDashboardData();
      setData(nextData);
      setSelectedIncidentId((current) =>
        current && nextData.incidents.some((item) => item.incident_id === current)
          ? current
          : (nextData.incidents.find(
              (item) =>
                !["APPROVED", "CLOSED", "FAILED"].includes(item.status),
            )?.incident_id ??
            nextData.incidents[0]?.incident_id ??
            null),
      );
      setLastUpdated(new Date());
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load dashboard data",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDetail = useCallback(async (incidentId: string) => {
    setDetailLoading(true);
    setError(null);
    try {
      setDetail(await getIncidentDetail(incidentId));
    } catch (caught) {
      setDetail(null);
      setError(
        caught instanceof Error ? caught.message : "Unable to load incident detail",
      );
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (selectedIncidentId) void loadDetail(selectedIncidentId);
    else setDetail(null);
  }, [loadDetail, selectedIncidentId]);

  const runSelectedInvestigation = useCallback(async () => {
    if (!selectedIncidentId) return;
    setRunning(true);
    setError(null);
    setActionMessage(null);
    try {
      const result = await runInvestigation(selectedIncidentId);
      setActionMessage("Investigation started. Triage agents are preparing…");

      for (let attempt = 0; attempt < 200; attempt += 1) {
        const [nextData, nextDetail] = await Promise.all([
          getDashboardData(),
          getIncidentDetail(selectedIncidentId),
        ]);
        setData(nextData);
        setDetail(nextDetail);
        setLastUpdated(new Date());

        const workflow = nextDetail.workflow?.workflow_runs.find(
          (item) => item.workflow_run_id === result.workflow_run_id,
        );
        if (workflow?.state.phase_label) {
          setActionMessage(workflow.state.phase_label);
        }
        if (workflow && workflow.status !== "RUNNING") {
          if (workflow.status === "COMPLETED") {
            setActionMessage(
              workflow.state.phase === "WAITING_FOR_APPROVAL"
                ? "Investigation complete. The recommendation is ready for faculty review."
                : "Investigation complete and escalated for human review.",
            );
          } else {
            throw new Error(
              workflow.state.error ?? "The agent workflow could not complete.",
            );
          }
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
      }
      throw new Error("The workflow is still running. Refresh to see its latest progress.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Workflow failed to start");
    } finally {
      setRunning(false);
    }
  }, [selectedIncidentId]);

  return {
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
    refresh: loadDashboard,
    refreshDetail: () =>
      selectedIncidentId ? loadDetail(selectedIncidentId) : Promise.resolve(),
    runSelectedInvestigation,
  };
}
