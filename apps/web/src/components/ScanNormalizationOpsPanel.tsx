import { useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type ScanNormalizationIssueListResponse,
  type ScanNormalizationRunListResponse,
  type ScanNormalizationRunSummaryRead,
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

export function ScanNormalizationOpsPanel() {
  const [summary, setSummary] = useState<ScanNormalizationRunListResponse | null>(null);
  const [issues, setIssues] = useState<ScanNormalizationIssueListResponse | null>(null);
  const [failures, setFailures] = useState<ScanNormalizationRunSummaryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runsResp, issuesResp, failuresResp] = await Promise.all([
          apiClient.listOpsNormalizationRuns({ limit: 40, offset: 0 }),
          apiClient.listOpsNormalizationIssues({ limit: 50, offset: 0 }),
          apiClient.listOpsNormalizationFailures({ limit: 25, offset: 0 }),
        ]);
        if (ignore) return;
        setSummary(runsResp);
        setIssues(issuesResp);
        setFailures(failuresResp.items);
      } catch (loadErr) {
        if (ignore) return;
        setSummary(null);
        setIssues(null);
        setFailures([]);
        setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan normalization ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section
      id="scan-normalization-ops"
      className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/10 p-5 shadow-xl shadow-black/20"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan normalization ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Cross-owner visibility into failed preprocessing, issue frequency, scanner quality drift, and replay-safe
            normalization lineage.
          </p>
        </div>
        <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
          Ops / P40-02
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading scan normalization ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : summary && issues ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Runs" value={String(summary.pagination.total_count)} />
            <StatCard label="Replay-safe" value={String(summary.replay_safe_run_count)} />
            <StatCard label="Failures" value={String(failures.length)} />
            <StatCard label="Issue types" value={String(Object.keys(issues.issue_type_counts).length)} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Object.entries(issues.issue_type_counts).map(([issueType, count]) => (
              <StatCard key={issueType} label={issueType.replace(/_/g, " ")} value={String(count)} />
            ))}
          </div>
          <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/50">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="p-3">Run</th>
                  <th className="p-3">Image</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Orientation</th>
                  <th className="p-3">Issues</th>
                  <th className="p-3">Checksum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-slate-200">
                {summary.items.slice(0, 10).map((row) => (
                  <tr key={row.id} className="align-top">
                    <td className="p-3 font-mono">#{row.id}</td>
                    <td className="p-3 font-mono">#{row.scan_image_id}</td>
                    <td className="p-3">{row.normalization_status}</td>
                    <td className="p-3">{row.orientation_code}</td>
                    <td className="p-3">{row.issue_count}</td>
                    <td className="p-3 font-mono text-violet-100">{row.normalization_checksum.slice(0, 12)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
}
