import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type ScanVisualEvidenceIssueListResponse,
  type ScanVisualEvidenceRunListResponse,
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

export function ScanVisualEvidenceOpsPanel() {
  const [runs, setRuns] = useState<ScanVisualEvidenceRunListResponse | null>(null);
  const [issues, setIssues] = useState<ScanVisualEvidenceIssueListResponse | null>(null);
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
          apiClient.listOpsScanVisualEvidenceRuns({ limit: 40, offset: 0 }),
          apiClient.listOpsScanVisualEvidenceIssues({ limit: 80, offset: 0 }),
          apiClient.listOpsScanVisualEvidenceFailures({ limit: 25, offset: 0 }),
        ]);
        if (ignore) return;
        setRuns(runResp);
        setIssues(issueResp);
        setFailures(failureResp.items.length);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load visual evidence ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const geometryIssues = useMemo(() => issues?.issue_type_counts.ANNOTATION_GEOMETRY_INVALID ?? 0, [issues]);
  const overlayIssues = useMemo(() => issues?.issue_type_counts.OVERLAY_GENERATION_FAILED ?? 0, [issues]);
  const incomplete = useMemo(() => issues?.issue_type_counts.REVIEW_PACKET_INCOMPLETE ?? 0, [issues]);

  return (
    <section id="scan-visual-evidence-ops" className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan visual evidence ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostic visibility into visual evidence failures, incomplete review packets, annotation geometry issues, overlay generation, and replay checksum validation.
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
          Ops / P40-13
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading visual evidence ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : runs && issues ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Runs" value={String(runs.pagination.total_count)} />
            <StatCard label="Failures" value={String(failures)} />
            <StatCard label="Incomplete packets" value={String(runs.incomplete_review_packet_count)} />
            <StatCard label="Low-confidence packages" value={String(runs.low_confidence_package_count)} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Geometry issues" value={String(geometryIssues)} />
            <StatCard label="Overlay issues" value={String(overlayIssues)} />
            <StatCard label="Incomplete review" value={String(incomplete)} />
          </div>
        </>
      ) : null}
    </section>
  );
}
