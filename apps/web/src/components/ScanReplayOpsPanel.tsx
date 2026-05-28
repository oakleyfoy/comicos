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

export function ScanReplayOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    runs: 0,
    critical: 0,
    failures: 0,
    lineageGaps: 0,
    nondeterminism: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runs, critical, failures, issues] = await Promise.all([
          apiClient.listOpsScanReplayRuns({ limit: 50, offset: 0 }),
          apiClient.listOpsScanReplayCritical({ limit: 100, offset: 0 }),
          apiClient.listOpsScanReplayFailures({ limit: 100, offset: 0 }),
          apiClient.listOpsScanReplayIssues({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          runs: runs.pagination.total_count,
          critical: critical.pagination.total_count,
          failures: failures.pagination.total_count,
          lineageGaps: issues.issue_type_counts.LINEAGE_INCOMPLETE ?? 0,
          nondeterminism: issues.issue_type_counts.NONDETERMINISM_DETECTED ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan replay ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="scan-replay-ops" className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan replay ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostics for checksum mismatches, lineage gaps, failed replays, and non-determinism alerts across the P40 verification ledger.
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
          Ops / P40-18
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading replay ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard label="Runs" value={String(stats.runs)} />
          <StatCard label="Critical discrepancies" value={String(stats.critical)} />
          <StatCard label="Failures" value={String(stats.failures)} />
          <StatCard label="Lineage gaps" value={String(stats.lineageGaps)} />
          <StatCard label="Non-determinism alerts" value={String(stats.nondeterminism)} />
        </div>
      )}
    </section>
  );
}
