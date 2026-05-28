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

export function AutomationJobsOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    queues: 0,
    failed: 0,
    deadLetter: 0,
    reservationConflicts: 0,
    dependencyConflicts: 0,
    criticalIssues: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [queues, failed, deadLetter, issues] = await Promise.all([
          apiClient.getOpsAutomationQueueHealth({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationFailedJobs({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationDeadLetterJobs({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationIssues({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          queues: queues.pagination.total_count,
          failed: failed.pagination.total_count,
          deadLetter: deadLetter.pagination.total_count,
          reservationConflicts: issues.items.filter((row) => row.issue_type === "DOUBLE_RESERVATION_ATTEMPT").length,
          dependencyConflicts: issues.items.filter((row) => row.issue_type === "DEPENDENCY_CYCLE_DETECTED").length,
          criticalIssues: issues.severity_counts.CRITICAL ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation queue ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-queue-ops" className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation queue ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostics for failed jobs, dead-letter queues, reservation conflicts, dependency conflicts, and replay-safe queue health.
          </p>
        </div>
        <span className="rounded-full border border-fuchsia-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-100/90">
          Ops / P41-01
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation queue ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <StatCard label="Queues" value={String(stats.queues)} />
          <StatCard label="Failed jobs" value={String(stats.failed)} />
          <StatCard label="Dead-letter jobs" value={String(stats.deadLetter)} />
          <StatCard label="Reservation conflicts" value={String(stats.reservationConflicts)} />
          <StatCard label="Dependency conflicts" value={String(stats.dependencyConflicts)} />
          <StatCard label="Critical issues" value={String(stats.criticalIssues)} />
        </div>
      )}
    </section>
  );
}
