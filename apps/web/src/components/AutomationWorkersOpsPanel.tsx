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

export function AutomationWorkersOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    workers: 0,
    stale: 0,
    active: 0,
    overloaded: 0,
    issues: 0,
    critical: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [workers, stale, issues] = await Promise.all([
          apiClient.listOpsAutomationWorkers({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationStaleWorkers({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationWorkerIssues({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          workers: workers.pagination.total_count,
          stale: stale.pagination.total_count,
          active: workers.active_execution_count,
          overloaded: workers.items.filter((row) => row.worker_status === "ERROR").length,
          issues: issues.pagination.total_count,
          critical: issues.severity_counts.CRITICAL ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load worker runtime ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-worker-ops" className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation worker ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostics for stale workers, active leases, failed executions, runtime conflicts, and checksum-safe execution visibility.
          </p>
        </div>
        <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
          Ops / P41-02
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation worker ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <StatCard label="Workers" value={String(stats.workers)} />
          <StatCard label="Stale workers" value={String(stats.stale)} />
          <StatCard label="Active executions" value={String(stats.active)} />
          <StatCard label="Errored workers" value={String(stats.overloaded)} />
          <StatCard label="Runtime issues" value={String(stats.issues)} />
          <StatCard label="Critical issues" value={String(stats.critical)} />
        </div>
      )}
    </section>
  );
}
