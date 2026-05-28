import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationWorkflowRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationWorkflowsSummaryCard() {
  const [latestWorkflow, setLatestWorkflow] = useState<AutomationWorkflowRead | null>(null);
  const [stats, setStats] = useState({ blocked: 0, failed: 0, pending: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [workflows, triggers] = await Promise.all([
          apiClient.listAutomationWorkflows({ limit: 12, offset: 0 }),
          apiClient.listAutomationTriggers({ limit: 25, offset: 0 }),
        ]);
        if (ignore) return;
        setLatestWorkflow(workflows.items[0] ?? null);
        setStats({
          blocked: workflows.blocked_workflow_count,
          failed: workflows.failed_execution_count,
          pending: triggers.pending_trigger_count,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load workflow orchestration summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latestWorkflow) return null;

  return (
    <section className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Workflow orchestration</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Scheduling and trigger summary</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic schedule activation, trigger intake, blocked workflow visibility, and replay-safe execution lineage.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-workflows" className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100">
            Open workflow workspace
          </Link>
          <Link to="/ops#automation-workflow-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading workflow orchestration summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestWorkflow ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest workflow" value={latestWorkflow.workflow_name} />
          <StatCard label="Status" value={latestWorkflow.workflow_status} />
          <StatCard label="Blocked workflows" value={String(stats.blocked)} />
          <StatCard label="Failed exec / pending" value={`${stats.failed} / ${stats.pending}`} />
        </div>
      ) : null}
    </section>
  );
}
