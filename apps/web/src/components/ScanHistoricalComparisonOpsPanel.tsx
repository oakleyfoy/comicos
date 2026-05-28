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

export function ScanHistoricalComparisonOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    runs: 0,
    failures: 0,
    inconclusive: 0,
    noPrior: 0,
    lowMatch: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runs, issues, failures, inconclusive] = await Promise.all([
          apiClient.listOpsScanHistoricalComparisonRuns({ limit: 50, offset: 0 }),
          apiClient.listOpsScanHistoricalComparisonIssues({ limit: 100, offset: 0 }),
          apiClient.listOpsScanHistoricalComparisonFailures({ limit: 50, offset: 0 }),
          apiClient.listOpsScanHistoricalComparisonInconclusive({ limit: 50, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          runs: runs.pagination.total_count,
          failures: failures.pagination.total_count,
          inconclusive: inconclusive.pagination.total_count,
          noPrior: issues.issue_type_counts.NO_PRIOR_SCAN_FOUND ?? 0,
          lowMatch: issues.issue_type_counts.LOW_MATCH_CONFIDENCE ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load historical comparison ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="scan-historical-comparison-ops" className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Historical comparison ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostics for comparison failures, no-prior-scan counts, low match confidence, inconclusive comparison runs, and replay checksum validation.
          </p>
        </div>
        <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
          Ops / P40-15
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading historical comparison ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard label="Runs" value={String(stats.runs)} />
          <StatCard label="Failures" value={String(stats.failures)} />
          <StatCard label="Inconclusive" value={String(stats.inconclusive)} />
          <StatCard label="No prior scan" value={String(stats.noPrior)} />
          <StatCard label="Low match" value={String(stats.lowMatch)} />
        </div>
      )}
    </section>
  );
}
