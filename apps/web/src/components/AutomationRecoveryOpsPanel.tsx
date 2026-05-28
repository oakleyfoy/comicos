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

export function AutomationRecoveryOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    runs: 0,
    deadLetter: 0,
    critical: 0,
    replayConflicts: 0,
    retryExhausted: 0,
    staleRecoveries: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runs, deadLetter, failures, critical] = await Promise.all([
          apiClient.listOpsAutomationRecoveryRuns({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationDeadLetterJobs({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationFailureEvents({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationRecoveryCritical({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          runs: runs.pagination.total_count,
          deadLetter: deadLetter.pagination.total_count,
          critical: critical.pagination.total_count,
          replayConflicts: critical.items.filter((row) => row.issue_type === "REPLAY_RECOVERY_CONFLICT").length,
          retryExhausted: critical.items.filter((row) => row.issue_type === "RETRY_EXHAUSTED").length,
          staleRecoveries: failures.items.filter((row) => row.failure_type === "HEARTBEAT_LOSS" || row.failure_type === "LEASE_TIMEOUT").length,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation recovery ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-recovery-ops" className="mt-6 rounded-3xl border border-rose-400/35 bg-rose-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation recovery ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostics for retry exhaustion, dead-letter routing, stale execution recovery, replay recovery conflicts, and critical recovery lineage issues.
          </p>
        </div>
        <span className="rounded-full border border-rose-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-rose-100/90">
          Ops / P41-04
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation recovery ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <StatCard label="Recovery runs" value={String(stats.runs)} />
          <StatCard label="Dead-letter jobs" value={String(stats.deadLetter)} />
          <StatCard label="Critical issues" value={String(stats.critical)} />
          <StatCard label="Replay conflicts" value={String(stats.replayConflicts)} />
          <StatCard label="Retry exhausted" value={String(stats.retryExhausted)} />
          <StatCard label="Stale recoveries" value={String(stats.staleRecoveries)} />
        </div>
      )}
    </section>
  );
}
