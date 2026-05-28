import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanDefectAggregationRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanDefectAggregationSummaryCard() {
  const [latestRun, setLatestRun] = useState<ScanDefectAggregationRunRead | null>(null);
  const [density, setDensity] = useState("0.000");
  const [issueCount, setIssueCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanDefectAggregationRuns({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatestRun(resp.items[0] ?? null);
        setDensity(resp.aggregate_anomaly_density.toFixed(3));
        setIssueCount(resp.unresolved_issue_count);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load aggregation summary.");
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
    <section className="mt-6 rounded-3xl border border-emerald-400/25 bg-emerald-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/70">Defect aggregation engine</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Unified condition aggregation</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic consolidation of defect, spine, corner/edge, surface, and structural evidence into replay-safe clusters and region summaries.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/scan-defect-aggregation" className="rounded-full border border-emerald-400/35 px-3 py-1.5 text-xs font-semibold text-emerald-100">
            Open aggregation workspace
          </Link>
          <Link to="/ops#scan-defect-aggregation-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading aggregation summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest run" value={`#${latestRun.id}`} />
          <StatCard label="Status" value={latestRun.aggregation_status} />
          <StatCard label="Aggregate density" value={density} />
          <StatCard label="Open issues" value={String(issueCount)} />
        </div>
      ) : null}
    </section>
  );
}
