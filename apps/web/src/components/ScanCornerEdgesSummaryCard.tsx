import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanCornerEdgeRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanCornerEdgesSummaryCard() {
  const [latestRun, setLatestRun] = useState<ScanCornerEdgeRunRead | null>(null);
  const [lowConfidence, setLowConfidence] = useState(0);
  const [highDensity, setHighDensity] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanCornerEdgeRuns({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatestRun(resp.items[0] ?? null);
        setLowConfidence(resp.low_confidence_count);
        setHighDensity(resp.high_density_wear_count);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load corner/edge summary.");
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
    <section className="mt-6 rounded-3xl border border-amber-400/25 bg-amber-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-amber-200/70">Corner / edge wear</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Border deterioration health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic corner rounding, edge chip, and border continuity evidence built on the defect foundation.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/scan-corner-edges" className="rounded-full border border-amber-400/35 px-3 py-1.5 text-xs font-semibold text-amber-100">
            Open corner/edge workspace
          </Link>
          <Link to="/ops#scan-corner-edges-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading corner/edge summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest run" value={`#${latestRun.id}`} />
          <StatCard label="Status" value={latestRun.detection_status} />
          <StatCard label="Low-confidence scans" value={String(lowConfidence)} />
          <StatCard label="High-density wear" value={String(highDensity)} />
        </div>
      ) : null}
    </section>
  );
}
