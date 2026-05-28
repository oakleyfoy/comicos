import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanGradingAssistanceRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanGradingAssistanceSummaryCard() {
  const [latestRun, setLatestRun] = useState<ScanGradingAssistanceRunRead | null>(null);
  const [reviewRequired, setReviewRequired] = useState(0);
  const [lowConfidence, setLowConfidence] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanGradingAssistanceRuns({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatestRun(resp.items[0] ?? null);
        setReviewRequired(resp.review_required_count);
        setLowConfidence(resp.low_confidence_support_count);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading assistance summary.");
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
    <section className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-violet-200/70">Grading assistance engine</p>
          <h2 className="mt-1 text-lg font-semibold text-white">PSA-aligned support health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic support ranges, pressure hints, and review flags derived from aggregated condition evidence without assigning an official grade.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/scan-grading-assistance" className="rounded-full border border-violet-400/35 px-3 py-1.5 text-xs font-semibold text-violet-100">
            Open grading workspace
          </Link>
          <Link to="/ops#scan-grading-assistance-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading grading assistance summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest run" value={`#${latestRun.id}`} />
          <StatCard label="Status" value={latestRun.assistance_status} />
          <StatCard label="Review required" value={String(reviewRequired)} />
          <StatCard label="Low confidence support" value={String(lowConfidence)} />
        </div>
      ) : null}
    </section>
  );
}
