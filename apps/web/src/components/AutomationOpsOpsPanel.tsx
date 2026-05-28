import { useEffect, useState } from "react";

import { ApiError, apiClient, type AutomationOpsSystemHealthRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationOpsOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<AutomationOpsSystemHealthRead | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient.listOpsAutomationSystemHealth();
        if (!ignore) setHealth(data);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation ops diagnostics.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-ops-dashboard" className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation ops dashboard</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Unified system health, replay integrity diagnostics, queue/runtime visibility, batch and recovery diagnostics, audit failures, and safe admin controls.
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
          Ops / P41-07
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation ops diagnostics…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : health ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <StatCard label="Status" value={health.snapshot_status} />
          <StatCard label="Queue depth" value={String(health.queue_depth)} />
          <StatCard label="Workers" value={String(health.active_workers)} />
          <StatCard label="Replay warnings" value={String(health.replay_warning_count)} />
          <StatCard label="Critical issues" value={String(health.critical_issue_count)} />
          <StatCard label="Failed audits" value={String(health.failed_audit_count)} />
        </div>
      ) : null}
    </section>
  );
}
