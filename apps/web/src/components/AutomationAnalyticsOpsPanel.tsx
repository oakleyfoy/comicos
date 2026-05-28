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

export function AutomationAnalyticsOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({ analytics: 0, failures: 0, drift: 0, utilization: 0 });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [snapshots, failures, drift] = await Promise.all([
          apiClient.listOpsAutomationAnalytics({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationAnalyticsFailures({ limit: 100, offset: 0 }),
          apiClient.listAutomationAnalyticsIssues({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          analytics: snapshots.pagination.total_count,
          failures: failures.pagination.total_count,
          drift: drift.replay_drift_count ?? 0,
          utilization: snapshots.utilization_warning_count ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation analytics ops diagnostics.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-analytics-ops" className="mt-6 rounded-3xl border border-emerald-400/35 bg-emerald-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation analytics ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Replay analytics diagnostics, trend failures, comparison conflicts, utilization warnings, throughput diagnostics, and checksum visibility.
          </p>
        </div>
        <span className="rounded-full border border-emerald-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100/90">
          Ops / P41-09
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation analytics diagnostics…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Analytics snapshots" value={String(stats.analytics)} />
          <StatCard label="Failures" value={String(stats.failures)} />
          <StatCard label="Replay drift" value={String(stats.drift)} />
          <StatCard label="Utilization warnings" value={String(stats.utilization)} />
        </div>
      )}
    </section>
  );
}
