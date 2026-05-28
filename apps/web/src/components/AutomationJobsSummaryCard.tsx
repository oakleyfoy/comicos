import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationJobRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationJobsSummaryCard() {
  const [latestJob, setLatestJob] = useState<AutomationJobRead | null>(null);
  const [stats, setStats] = useState({ failed: 0, deadLetter: 0, reserved: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await apiClient.listAutomationJobs({ limit: 12, offset: 0 });
        if (ignore) return;
        setLatestJob(response.items[0] ?? null);
        setStats({
          failed: response.failed_job_count,
          deadLetter: response.dead_letter_count,
          reserved: response.reserved_job_count,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation queue summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latestJob) return null;

  return (
    <section className="mt-6 rounded-3xl border border-fuchsia-400/25 bg-fuchsia-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-fuchsia-200/70">Automation queue</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Job ledger summary</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic queue health for replay-safe jobs, failure visibility, dead-letter counts, and reservation state.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-jobs" className="rounded-full border border-fuchsia-400/35 px-3 py-1.5 text-xs font-semibold text-fuchsia-100">
            Open queue workspace
          </Link>
          <Link to="/ops#automation-queue-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation queue summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestJob ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest job" value={`#${latestJob.id}`} />
          <StatCard label="Status" value={latestJob.job_status} />
          <StatCard label="Failed jobs" value={String(stats.failed)} />
          <StatCard label="Dead-letter / reserved" value={`${stats.deadLetter} / ${stats.reserved}`} />
        </div>
      ) : null}
    </section>
  );
}
