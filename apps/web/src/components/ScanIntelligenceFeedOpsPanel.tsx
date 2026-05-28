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

export function ScanIntelligenceFeedOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    runs: 0,
    errors: 0,
    reviewRequired: 0,
    lineageGaps: 0,
    failedRuns: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runs, issues, failures, reviewRequired] = await Promise.all([
          apiClient.listOpsScanIntelligenceFeedRuns({ limit: 50, offset: 0 }),
          apiClient.listOpsScanIntelligenceFeedIssues({ limit: 100, offset: 0 }),
          apiClient.listOpsScanIntelligenceFeedFailures({ limit: 100, offset: 0 }),
          apiClient.listOpsScanIntelligenceFeedReviewRequired({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          runs: runs.pagination.total_count,
          errors: failures.pagination.total_count,
          reviewRequired: reviewRequired.pagination.total_count,
          lineageGaps: issues.issue_type_counts.LINEAGE_GAP ?? 0,
          failedRuns: runs.status_counts.FAILED ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan intelligence feed ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="scan-intelligence-feed-ops" className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan intelligence feed ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostics for replay-safe timeline generation, lineage gaps, high-severity events, and review-required activity across the scan stack.
          </p>
        </div>
        <span className="rounded-full border border-fuchsia-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-100/90">
          Ops / P41-17
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading scan intelligence feed ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard label="Runs" value={String(stats.runs)} />
          <StatCard label="Failure events" value={String(stats.errors)} />
          <StatCard label="Review required" value={String(stats.reviewRequired)} />
          <StatCard label="Lineage gaps" value={String(stats.lineageGaps)} />
          <StatCard label="Failed runs" value={String(stats.failedRuns)} />
        </div>
      )}
    </section>
  );
}
