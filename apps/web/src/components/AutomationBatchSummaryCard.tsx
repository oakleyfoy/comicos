import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationBatchRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationBatchSummaryCard() {
  const [latestRun, setLatestRun] = useState<AutomationBatchRunRead | null>(null);
  const [stats, setStats] = useState({ failed: 0, maintenance: 0, integrity: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runs, issues] = await Promise.all([
          apiClient.listAutomationBatchRuns({ limit: 12, offset: 0 }),
          apiClient.listAutomationBatchIssues({ limit: 50, offset: 0 }),
        ]);
        if (ignore) return;
        setLatestRun(runs.items[0] ?? null);
        setStats({
          failed: runs.failed_batch_count,
          maintenance: runs.maintenance_job_count,
          integrity: issues.items.filter((row) => row.issue_type === "ORPHAN_ARTIFACT_DETECTED").length,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation batch summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latestRun) return null;

  return (
    <section className="mt-6 rounded-3xl border border-amber-400/25 bg-amber-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-amber-200/70">Automation batch</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Batch and maintenance summary</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic batch execution, maintenance audits, integrity warnings, and replay-safe chunk diagnostics.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-batch" className="rounded-full border border-amber-400/35 px-3 py-1.5 text-xs font-semibold text-amber-100">
            Open batch workspace
          </Link>
          <Link to="/ops#automation-batch-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation batch summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest batch" value={`#${latestRun.id}`} />
          <StatCard label="Type / status" value={`${latestRun.batch_type} / ${latestRun.batch_status}`} />
          <StatCard label="Failed batches" value={String(stats.failed)} />
          <StatCard label="Maint / warnings" value={`${stats.maintenance} / ${stats.integrity}`} />
        </div>
      ) : null}
    </section>
  );
}
