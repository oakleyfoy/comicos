import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanAuthenticationRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanAuthenticationSummaryCard() {
  const [latestRun, setLatestRun] = useState<ScanAuthenticationRunRead | null>(null);
  const [conflictCount, setConflictCount] = useState(0);
  const [reviewRequiredCount, setReviewRequiredCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanAuthenticationRuns({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatestRun(resp.items[0] ?? null);
        setConflictCount(resp.unresolved_conflict_count);
        setReviewRequiredCount(resp.review_required_count);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load authentication assistance summary.");
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
    <section className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Authentication assistance</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Authenticity review support health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic support signals, conflict flags, and lineage checks for human authenticity review.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/scan-authentication" className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100">
            Open authentication workspace
          </Link>
          <Link to="/ops#scan-authentication-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading authentication assistance summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest run" value={`#${latestRun.id}`} />
          <StatCard label="Status" value={latestRun.authentication_status} />
          <StatCard label="Open conflicts" value={String(conflictCount)} />
          <StatCard label="Review required" value={String(reviewRequiredCount)} />
        </div>
      ) : null}
    </section>
  );
}
