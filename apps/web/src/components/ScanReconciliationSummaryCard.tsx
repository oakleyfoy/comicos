import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanReconciliationRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanReconciliationSummaryCard() {
  const [latestRun, setLatestRun] = useState<ScanReconciliationRunRead | null>(null);
  const [ambiguousMatches, setAmbiguousMatches] = useState(0);
  const [lowConfidence, setLowConfidence] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanReconciliationRuns({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatestRun(resp.items[0] ?? null);
        setAmbiguousMatches(resp.ambiguous_match_count);
        setLowConfidence(resp.low_confidence_count);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load reconciliation summary.");
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
    <section className="mt-6 rounded-3xl border border-teal-400/25 bg-teal-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-teal-200/70">OCR reconciliation</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Canonical comic identity health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Recent reconciliation runs, ambiguous match counts, and low-confidence canonical decisions across OCR-derived scans.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/scan-reconciliation" className="rounded-full border border-teal-400/35 px-3 py-1.5 text-xs font-semibold text-teal-100">
            Open reconciliation
          </Link>
          <Link to="/ops#scan-reconciliation-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading reconciliation summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest run" value={`#${latestRun.id}`} />
          <StatCard label="Status" value={latestRun.reconciliation_status} />
          <StatCard label="Ambiguous" value={String(ambiguousMatches)} />
          <StatCard label="Low confidence" value={String(lowConfidence)} />
        </div>
      ) : null}
    </section>
  );
}
