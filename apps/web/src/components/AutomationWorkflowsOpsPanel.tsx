import { useEffect, useState } from "react";

import { ApiError, apiClient } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationWorkflowsOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    workflows: 0,
    blocked: 0,
    failed: 0,
    pending: 0,
    dependencyConflicts: 0,
    critical: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [workflows, blocked, triggers, issues] = await Promise.all([
          apiClient.listOpsAutomationWorkflows({ limit: 100, offset: 0 }),
          apiClient.listOpsBlockedAutomationWorkflows({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationTriggers({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationWorkflowIssues({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          workflows: workflows.pagination.total_count,
          blocked: blocked.pagination.total_count,
          failed: workflows.failed_execution_count,
          pending: triggers.pending_trigger_count,
          dependencyConflicts: issues.items.filter((row) => row.issue_type === "WORKFLOW_DEPENDENCY_CONFLICT").length,
          critical: issues.severity_counts.CRITICAL ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load workflow orchestration ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-workflow-ops" className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation workflow ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostics for blocked workflows, failed executions, pending triggers, schedule drift risks, dependency conflicts, and orchestration issues.
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
          Ops / P41-03
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading workflow orchestration ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <StatCard label="Workflows" value={String(stats.workflows)} />
          <StatCard label="Blocked workflows" value={String(stats.blocked)} />
          <StatCard label="Failed executions" value={String(stats.failed)} />
          <StatCard label="Pending triggers" value={String(stats.pending)} />
          <StatCard label="Dependency conflicts" value={String(stats.dependencyConflicts)} />
          <StatCard label="Critical issues" value={String(stats.critical)} />
        </div>
      )}
    </section>
  );
}
