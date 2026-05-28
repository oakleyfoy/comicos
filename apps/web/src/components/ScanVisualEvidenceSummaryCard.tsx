import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanVisualEvidenceRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanVisualEvidenceSummaryCard() {
  const [latestRun, setLatestRun] = useState<ScanVisualEvidenceRunRead | null>(null);
  const [incomplete, setIncomplete] = useState(0);
  const [lowConfidence, setLowConfidence] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanVisualEvidenceRuns({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatestRun(resp.items[0] ?? null);
        setIncomplete(resp.incomplete_review_packet_count);
        setLowConfidence(resp.low_confidence_package_count);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load visual evidence summary.");
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
    <section className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Visual evidence system</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Review packet health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Packages existing scan intelligence into overlays and exports without creating new defect or grade conclusions.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/scan-visual-evidence" className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100">
            Open visual evidence workspace
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading visual evidence summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest run" value={`#${latestRun.id}`} />
          <StatCard label="Status" value={latestRun.evidence_status} />
          <StatCard label="Incomplete packets" value={String(incomplete)} />
          <StatCard label="Low-confidence packages" value={String(lowConfidence)} />
        </div>
      ) : null}
    </section>
  );
}
