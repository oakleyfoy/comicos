import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationWorkerRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationWorkersSummaryCard() {
  const [latestWorker, setLatestWorker] = useState<AutomationWorkerRead | null>(null);
  const [stats, setStats] = useState({ stale: 0, active: 0, issues: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await apiClient.listAutomationWorkers({ limit: 12, offset: 0 });
        if (ignore) return;
        setLatestWorker(response.items[0] ?? null);
        setStats({
          stale: response.stale_count,
          active: response.active_execution_count,
          issues: response.runtime_issue_count,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load worker runtime summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latestWorker) return null;

  return (
    <section className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-violet-200/70">Worker runtime</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Execution runtime summary</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic worker health for stale heartbeats, active executions, and runtime issue visibility.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-workers" className="rounded-full border border-violet-400/35 px-3 py-1.5 text-xs font-semibold text-violet-100">
            Open worker workspace
          </Link>
          <Link to="/ops#automation-worker-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading worker runtime summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestWorker ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest worker" value={latestWorker.worker_identifier} />
          <StatCard label="Status" value={latestWorker.worker_status} />
          <StatCard label="Stale workers" value={String(stats.stale)} />
          <StatCard label="Active exec / issues" value={`${stats.active} / ${stats.issues}`} />
        </div>
      ) : null}
    </section>
  );
}
