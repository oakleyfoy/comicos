import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationAnalyticsSnapshotRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationAnalyticsSummaryCard() {
  const [latest, setLatest] = useState<AutomationAnalyticsSnapshotRead | null>(null);
  const [stats, setStats] = useState({ replay: 0, utilization: 0, failure: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const snapshots = await apiClient.listAutomationAnalyticsSnapshots({ limit: 12, offset: 0 });
        if (ignore) return;
        setLatest((snapshots.items[0] as AutomationAnalyticsSnapshotRead | undefined) ?? null);
        setStats({
          replay: snapshots.replay_drift_count ?? 0,
          utilization: snapshots.utilization_warning_count ?? 0,
          failure: snapshots.failure_warning_count ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation analytics summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latest) return null;

  return (
    <section className="mt-6 rounded-3xl border border-emerald-400/25 bg-emerald-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/70">Automation analytics</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Operational intelligence summary</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">Deterministic analytics snapshots, replay trends, and comparison visibility.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-analytics" className="rounded-full border border-emerald-400/35 px-3 py-1.5 text-xs font-semibold text-emerald-100">
            Open analytics workspace
          </Link>
          <Link to="/ops#automation-analytics-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation analytics summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latest ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest snapshot" value={`#${latest.id} / ${latest.analytics_status}`} />
          <StatCard label="Replay drift" value={String(stats.replay)} />
          <StatCard label="Utilization warnings" value={String(stats.utilization)} />
          <StatCard label="Failure warnings" value={String(stats.failure)} />
        </div>
      ) : null}
    </section>
  );
}
