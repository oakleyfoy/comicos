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

export function ScanReviewOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    runs: 0,
    blocked: 0,
    rescans: 0,
    issues: 0,
    reviewBlockedIssues: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runs, issues, blocked, rescans] = await Promise.all([
          apiClient.listOpsScanReviewSessions({ limit: 50, offset: 0 }),
          apiClient.listOpsScanReviewIssues({ limit: 100, offset: 0 }),
          apiClient.listOpsScanReviewBlocked({ limit: 50, offset: 0 }),
          apiClient.listOpsScanReviewRescans({ limit: 50, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          runs: runs.pagination.total_count,
          blocked: blocked.pagination.total_count,
          rescans: rescans.pagination.total_count,
          issues: issues.pagination.total_count,
          reviewBlockedIssues: issues.issue_type_counts.REVIEW_BLOCKED ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load review workspace ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="scan-review-ops" className="mt-6 rounded-3xl border border-amber-400/35 bg-amber-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan review ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostic visibility into blocked reviews, open review-required flags, rescan requests, completion throughput, and replay checksum validation.
          </p>
        </div>
        <span className="rounded-full border border-amber-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/90">
          Ops / P40-14
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading review workspace ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard label="Sessions" value={String(stats.runs)} />
          <StatCard label="Blocked reviews" value={String(stats.blocked)} />
          <StatCard label="Rescan requests" value={String(stats.rescans)} />
          <StatCard label="Open issues" value={String(stats.issues)} />
          <StatCard label="Review blocked" value={String(stats.reviewBlockedIssues)} />
        </div>
      )}
    </section>
  );
}
