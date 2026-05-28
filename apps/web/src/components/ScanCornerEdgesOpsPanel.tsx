import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type ScanCornerEdgeIssueListResponse,
  type ScanCornerEdgeRunListResponse,
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

export function ScanCornerEdgesOpsPanel() {
  const [runs, setRuns] = useState<ScanCornerEdgeRunListResponse | null>(null);
  const [issues, setIssues] = useState<ScanCornerEdgeIssueListResponse | null>(null);
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
          apiClient.listOpsScanCornerEdgeRuns({ limit: 40, offset: 0 }),
          apiClient.listOpsScanCornerEdgeIssues({ limit: 80, offset: 0 }),
          apiClient.listOpsScanCornerEdgeFailures({ limit: 25, offset: 0 }),
        ]);
        if (ignore) return;
        setRuns(runResp);
        setIssues(issueResp);
        setFailures(failureResp.items.length);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load corner/edge ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const glareCount = useMemo(() => issues?.issue_type_counts.EXCESSIVE_GLARE ?? 0, [issues]);
  const borderFailCount = useMemo(() => issues?.issue_type_counts.BORDER_SEGMENTATION_FAILED ?? 0, [issues]);

  return (
    <section id="scan-corner-edges-ops" className="mt-6 rounded-3xl border border-amber-400/35 bg-amber-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan corner/edge ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostic visibility into wear detection failures, glare/noise frequency, replay checksum validation, evidence density, and border continuity diagnostics.
          </p>
        </div>
        <span className="rounded-full border border-amber-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/90">
          Ops / P40-08
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading corner/edge ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : runs && issues ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Runs" value={String(runs.pagination.total_count)} />
            <StatCard label="Failures" value={String(failures)} />
            <StatCard label="Low-confidence (page)" value={String(runs.low_confidence_count)} />
            <StatCard label="High-density wear" value={String(runs.high_density_wear_count)} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Glare diagnostics" value={String(glareCount)} />
            <StatCard label="Border segmentation" value={String(borderFailCount)} />
            {Object.entries(issues.issue_type_counts)
              .slice(0, 6)
              .map(([issueType, count]) => (
                <StatCard key={issueType} label={issueType.replace(/_/g, " ")} value={String(count)} />
              ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
