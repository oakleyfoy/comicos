import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type ScanStructuralDamageIssueListResponse,
  type ScanStructuralDamageRunListResponse,
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

export function ScanStructuralDamageOpsPanel() {
  const [runs, setRuns] = useState<ScanStructuralDamageRunListResponse | null>(null);
  const [issues, setIssues] = useState<ScanStructuralDamageIssueListResponse | null>(null);
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
          apiClient.listOpsScanStructuralDamageRuns({ limit: 40, offset: 0 }),
          apiClient.listOpsScanStructuralDamageIssues({ limit: 80, offset: 0 }),
          apiClient.listOpsScanStructuralDamageFailures({ limit: 25, offset: 0 }),
        ]);
        if (ignore) return;
        setRuns(runResp);
        setIssues(issueResp);
        setFailures(failureResp.items.length);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load structural ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const glareCount = useMemo(() => issues?.issue_type_counts.EXCESSIVE_GLARE ?? 0, [issues]);
  const noiseCount = useMemo(() => issues?.issue_type_counts.EXCESSIVE_BACKGROUND_NOISE ?? 0, [issues]);
  const alignmentCount = useMemo(() => issues?.issue_type_counts.LOW_ALIGNMENT_CONFIDENCE ?? 0, [issues]);

  return (
    <section id="scan-structural-damage-ops" className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan structural damage ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostic visibility into structural detection failures, glare/noise frequency, replay checksum validation, evidence density distributions, and alignment geometry stability.
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
          Ops / P40-10
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading structural ops…</p>
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
            <StatCard label="Major anomalies" value={String(runs.major_structural_count)} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Glare diagnostics" value={String(glareCount)} />
            <StatCard label="Background noise" value={String(noiseCount)} />
            <StatCard label="Alignment warnings" value={String(alignmentCount)} />
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
