import { useEffect, useState } from "react";

import { ApiError, apiClient, type ScanImageSummaryRead, type ScanIngestionBatchListResponse } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanIngestionOpsPanel() {
  const [summary, setSummary] = useState<ScanIngestionBatchListResponse | null>(null);
  const [failures, setFailures] = useState<ScanImageSummaryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [batches, failed] = await Promise.all([
          apiClient.listOpsScanBatches({ limit: 40, offset: 0 }),
          apiClient.listOpsScanFailures({ limit: 25, offset: 0 }),
        ]);
        if (ignore) return;
        setSummary(batches);
        setFailures(failed.items);
      } catch (loadErr) {
        if (ignore) return;
        setSummary(null);
        setFailures([]);
        setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan ingestion ops data.");
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
      id="scan-ingestion-ops"
      className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/20"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan ingestion ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Cross-owner visibility into failed ingestions, duplicate detections, and source mix for the immutable P40 scan
            intake ledger.
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
          Ops / P40-01
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading scan ingestion ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : summary ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Batches" value={String(summary.pagination.total_count)} />
            <StatCard label="Duplicates" value={String(summary.duplicate_image_count)} />
            <StatCard label="Failures" value={String(summary.failed_image_count)} />
            <StatCard label="Active sources" value={String(Object.keys(summary.source_type_counts).length)} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Object.entries(summary.source_type_counts).map(([sourceType, count]) => (
              <StatCard key={sourceType} label={sourceType.replace(/_/g, " ")} value={String(count)} />
            ))}
          </div>
          <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/50">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="p-3">Image</th>
                  <th className="p-3">Batch</th>
                  <th className="p-3">Filename</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Duplicate</th>
                  <th className="p-3">Failure</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-slate-200">
                {failures.map((row) => (
                  <tr key={row.id} className="align-top">
                    <td className="p-3 font-mono">#{row.id}</td>
                    <td className="p-3 font-mono">#{row.ingestion_batch_id}</td>
                    <td className="p-3">{row.original_filename}</td>
                    <td className="p-3">{row.processing_status}</td>
                    <td className="p-3">{row.is_duplicate ? `#${row.duplicate_of_scan_image_id}` : "—"}</td>
                    <td className="max-w-[20rem] p-3 text-rose-200/95">{row.failure_reason ?? "—"}</td>
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
