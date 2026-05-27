import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanIngestionBatchSummaryRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function batchTone(status: string): string {
  switch (status) {
    case "COMPLETE":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "PROCESSING":
    case "PENDING":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "FAILED":
    default:
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
  }
}

export function ScanIngestionSummaryCard() {
  const [latestBatch, setLatestBatch] = useState<ScanIngestionBatchSummaryRead | null>(null);
  const [duplicateCount, setDuplicateCount] = useState(0);
  const [failedCount, setFailedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanBatches({ limit: 10, offset: 0 });
        if (ignore) return;
        setLatestBatch(resp.items[0] ?? null);
        setDuplicateCount(resp.duplicate_image_count);
        setFailedCount(resp.failed_image_count);
      } catch (loadErr) {
        if (ignore) return;
        setLatestBatch(null);
        setDuplicateCount(0);
        setFailedCount(0);
        setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan ingestion summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latestBatch) {
    return null;
  }

  return (
    <section className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Scan ingestion</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Deterministic visual intake</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Immutable originals, duplicate warnings, and append-only batch registration for the new P40 visual ingest layer.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/scan-ingestion"
            className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-500/10"
          >
            Open uploads
          </Link>
          <Link
            to="/ops#scan-ingestion-ops"
            className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-cyan-300/35 hover:bg-white/5"
          >
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading scan ingestion summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestBatch ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Latest batch" value={`#${latestBatch.id}`} />
            <StatCard label="Images" value={String(latestBatch.image_count)} />
            <StatCard label="Duplicates" value={String(duplicateCount)} />
            <StatCard label="Failures" value={String(failedCount)} />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-300">
            <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${batchTone(latestBatch.batch_status)}`}>
              {latestBatch.batch_status}
            </span>
            <span>
              Source <span className="font-semibold text-white">{latestBatch.source_type}</span>
            </span>
            <span>
              Checksum <span className="font-mono text-cyan-100">{latestBatch.ingestion_checksum.slice(0, 12)}…</span>
            </span>
          </div>
        </>
      ) : null}
    </section>
  );
}
