import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationOpsSnapshotRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationOpsSummaryCard() {
  const [latest, setLatest] = useState<AutomationOpsSnapshotRead | null>(null);
  const [stats, setStats] = useState({ replayWarnings: 0, criticalIssues: 0, failedAudits: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const snapshots = await apiClient.listAutomationOpsSnapshots({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatest((snapshots.items[0] as AutomationOpsSnapshotRead | undefined) ?? null);
        setStats({
          replayWarnings: snapshots.replay_warning_count ?? 0,
          criticalIssues: snapshots.critical_issue_count ?? 0,
          failedAudits: snapshots.failed_audit_count ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation ops summary.");
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
    <section className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Automation ops</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Unified automation health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">Replay-safe ops snapshots, audit lineage, and critical issue visibility.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-ops" className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100">
            Open ops dashboard
          </Link>
          <Link to="/ops#automation-ops-dashboard" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation ops summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latest ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest snapshot" value={`#${latest.id} / ${latest.snapshot_status}`} />
          <StatCard label="Replay warnings" value={String(stats.replayWarnings)} />
          <StatCard label="Critical issues" value={String(stats.criticalIssues)} />
          <StatCard label="Failed audits" value={String(stats.failedAudits)} />
        </div>
      ) : null}
    </section>
  );
}
