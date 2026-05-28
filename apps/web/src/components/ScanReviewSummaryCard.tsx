import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanReviewSessionRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanReviewSummaryCard() {
  const [latestSession, setLatestSession] = useState<ScanReviewSessionRead | null>(null);
  const [blockedCount, setBlockedCount] = useState(0);
  const [rescanCount, setRescanCount] = useState(0);
  const [completedCount, setCompletedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanReviewSessions({ limit: 8, offset: 0 });
        if (ignore) return;
        setLatestSession(resp.items[0] ?? null);
        setBlockedCount(resp.blocked_review_count);
        setRescanCount(resp.rescan_request_count);
        setCompletedCount(resp.completed_review_count);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load review workspace summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latestSession) return null;

  return (
    <section className="mt-6 rounded-3xl border border-amber-400/25 bg-amber-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-amber-200/70">Review workspace</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Human review health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Append-only reviewer decisions, notes, and evidence actions over immutable scan intelligence.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/scan-review" className="rounded-full border border-amber-400/35 px-3 py-1.5 text-xs font-semibold text-amber-100">
            Open review workspace
          </Link>
          <Link to="/ops#scan-review-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading review workspace summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latestSession ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest session" value={`#${latestSession.id}`} />
          <StatCard label="Status" value={latestSession.review_status} />
          <StatCard label="Blocked reviews" value={String(blockedCount)} />
          <StatCard label="Completed reviews" value={String(completedCount)} />
          <StatCard label="Rescan requests" value={String(rescanCount)} />
        </div>
      ) : null}
    </section>
  );
}
