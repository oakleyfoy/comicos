import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanNormalizationRunSummaryRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function tone(status: string): string {
  switch (status) {
    case "COMPLETE":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "FAILED":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
  }
}

export function ScanNormalizationSummaryCard() {
  const [latestRun, setLatestRun] = useState<ScanNormalizationRunSummaryRead | null>(null);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [replaySafeRunCount, setReplaySafeRunCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listNormalizationRuns({ limit: 10, offset: 0 });
        if (ignore) return;
        setLatestRun(resp.items[0] ?? null);
        setStatusCounts(resp.status_counts);
        setReplaySafeRunCount(resp.replay_safe_run_count);
      } catch (loadErr) {
        if (ignore) return;
        setLatestRun(null);
        setStatusCounts({});
        setReplaySafeRunCount(0);
        setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan normalization summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latestRun) {
    return null;
  }

  return (
    <section className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-violet-200/70">Scan normalization</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Deterministic preprocessing health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Replay-safe normalization runs, checksum lineage, and issue visibility for the P40 image-prep layer.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/scan-normalization"
            className="rounded-full border border-violet-400/35 px-3 py-1.5 text-xs font-semibold text-violet-100 transition hover:border-violet-300/60 hover:bg-violet-500/10"
          >
            Open normalization
          </Link>
          <Link
            to="/ops#scan-normalization-ops"
            className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-violet-300/35 hover:bg-white/5"
          >
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading scan normalization summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestRun ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Latest run" value={`#${latestRun.id}`} />
            <StatCard label="Artifacts" value={String(latestRun.artifact_count)} />
            <StatCard label="Issues" value={String(latestRun.issue_count)} />
            <StatCard label="Replay-safe runs" value={String(replaySafeRunCount)} />
          </div>
          <div className="mt-4 flex flex-wrap gap-3 text-sm text-slate-300">
            <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${tone(latestRun.normalization_status)}`}>
              {latestRun.normalization_status}
            </span>
            <span>
              Orientation <span className="font-semibold text-white">{latestRun.orientation_code}</span>
            </span>
            <span>
              Complete <span className="font-semibold text-white">{String(statusCounts.COMPLETE ?? 0)}</span>
            </span>
            <span>
              Failed <span className="font-semibold text-white">{String(statusCounts.FAILED ?? 0)}</span>
            </span>
          </div>
        </>
      ) : null}
    </section>
  );
}
