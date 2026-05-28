import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanReplayRunRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanReplaySummaryCard() {
  const [latestRun, setLatestRun] = useState<ScanReplayRunRead | null>(null);
  const [totals, setTotals] = useState({ critical: 0, mismatches: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await apiClient.listScanReplayRuns({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatestRun(response.items[0] ?? null);
        setTotals({
          critical: response.critical_discrepancy_count,
          mismatches: response.mismatch_count,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load replay summary.");
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
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Determinism / replay</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Replay health summary</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Audit-grade replay verification for checksum lineage, immutable artifacts, and critical discrepancy visibility.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/scan-replay" className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100">
            Open replay workspace
          </Link>
          <Link to="/ops#scan-replay-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading replay summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest run" value={`#${latestRun.id}`} />
          <StatCard label="Status" value={latestRun.replay_status} />
          <StatCard label="Critical discrepancies" value={String(totals.critical)} />
          <StatCard label="Checksum mismatches" value={String(totals.mismatches)} />
        </div>
      ) : null}
    </section>
  );
}
