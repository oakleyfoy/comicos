import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type ScanDefectAggregationIssueListResponse,
  type ScanDefectAggregationRunListResponse,
} from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanDefectAggregationOpsPanel() {
  const [runs, setRuns] = useState<ScanDefectAggregationRunListResponse | null>(null);
  const [issues, setIssues] = useState<ScanDefectAggregationIssueListResponse | null>(null);
  const [failures, setFailures] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runResp, issueResp, failureResp] = await Promise.all([
          apiClient.listOpsScanDefectAggregationRuns({ limit: 40, offset: 0 }),
          apiClient.listOpsScanDefectAggregationIssues({ limit: 80, offset: 0 }),
          apiClient.listOpsScanDefectAggregationFailures({ limit: 25, offset: 0 }),
        ]);
        if (ignore) return;
        setRuns(runResp);
        setIssues(issueResp);
        setFailures(failureResp.items.length);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load aggregation ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const clusteringFailures = useMemo(() => issues?.issue_type_counts.CLUSTERING_FAILED ?? 0, [issues]);
  const overlapConflicts = useMemo(() => issues?.issue_type_counts.OVERLAPPING_REGION_CONFLICT ?? 0, [issues]);
  const geometryConflicts = useMemo(() => issues?.issue_type_counts.GEOMETRY_CONFLICT ?? 0, [issues]);

  return (
    <section id="scan-defect-aggregation-ops" className="mt-6 rounded-3xl border border-emerald-400/35 bg-emerald-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan defect aggregation ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostic visibility into clustering failures, replay checksum validation, aggregate evidence density, overlap conflicts, and detector contribution drift.
          </p>
        </div>
        <span className="rounded-full border border-emerald-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100/90">
          Ops / P40-11
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading aggregation ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : runs && issues ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Runs" value={String(runs.pagination.total_count)} />
            <StatCard label="Failures" value={String(failures)} />
            <StatCard label="Low-confidence clusters" value={String(runs.low_confidence_clusters)} />
            <StatCard label="Aggregate density" value={runs.aggregate_anomaly_density.toFixed(3)} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Clustering failures" value={String(clusteringFailures)} />
            <StatCard label="Overlap conflicts" value={String(overlapConflicts)} />
            <StatCard label="Geometry conflicts" value={String(geometryConflicts)} />
            {Object.entries(issues.issue_type_counts)
              .slice(0, 5)
              .map(([issueType, count]) => (
                <StatCard key={issueType} label={issueType.replace(/_/g, " ")} value={String(count)} />
              ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
