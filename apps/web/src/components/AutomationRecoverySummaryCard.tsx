import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationRecoveryRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationRecoverySummaryCard() {
  const [latestRun, setLatestRun] = useState<AutomationRecoveryRunRead | null>(null);
  const [stats, setStats] = useState({ deadLetter: 0, critical: 0, retries: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runs, issues] = await Promise.all([
          apiClient.listAutomationRecoveryRuns({ limit: 12, offset: 0 }),
          apiClient.listAutomationRecoveryIssues({ limit: 25, offset: 0 }),
        ]);
        if (ignore) return;
        setLatestRun(runs.items[0] ?? null);
        setStats({
          deadLetter: runs.dead_letter_count,
          critical: runs.critical_failure_count,
          retries: runs.items.filter((row) => row.recovery_type === "RETRY").length,
        });
        if (!runs.items.length && issues.items.length) {
          setStats((current) => ({ ...current, critical: issues.severity_counts.CRITICAL ?? current.critical }));
        }
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation recovery summary.");
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
    <section className="mt-6 rounded-3xl border border-rose-400/25 bg-rose-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-rose-200/70">Automation recovery</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Retry and dead-letter summary</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic retry scheduling, dead-letter visibility, stale execution recovery, and replay-safe failure lineage.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-recovery" className="rounded-full border border-rose-400/35 px-3 py-1.5 text-xs font-semibold text-rose-100">
            Open recovery workspace
          </Link>
          <Link to="/ops#automation-recovery-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation recovery summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest recovery" value={`#${latestRun.id}`} />
          <StatCard label="Type / status" value={`${latestRun.recovery_type} / ${latestRun.recovery_status}`} />
          <StatCard label="Dead-letter count" value={String(stats.deadLetter)} />
          <StatCard label="Retries / critical" value={`${stats.retries} / ${stats.critical}`} />
        </div>
      ) : null}
    </section>
  );
}
