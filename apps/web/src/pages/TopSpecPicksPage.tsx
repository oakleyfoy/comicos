import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type TopSpecPickRead, type TopSpecPickSummaryRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function scoreClass(score: number): string {
  if (score >= 70) return "text-emerald-300";
  if (score >= 45) return "text-cyan-200";
  return "text-slate-400";
}

function riskClass(level: string): string {
  if (level === "LOW") return "text-emerald-300";
  if (level === "MEDIUM") return "text-amber-200";
  return "text-rose-300";
}

export function TopSpecPicksPage(): JSX.Element {
  const [items, setItems] = useState<TopSpecPickRead[]>([]);
  const [summary, setSummary] = useState<TopSpecPickSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum] = await Promise.all([apiClient.getTopSpecPicks(), apiClient.getTopSpecPickSummary()]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load Top 20 spec picks.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefreshLatest() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const latest = await apiClient.runTopSpecPicks();
      setItems(latest.items);
      const sum = await apiClient.getTopSpecPickSummary();
      setSummary(sum);
      setMessage(
        latest.picks_skipped
          ? "Ranked set unchanged — skipped insert."
          : `Generated ${latest.picks_computed} Top spec pick(s).`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh Top 20 spec picks.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P60-04"
        title="Top 20 Spec Picks"
        description="Weekly preorder shortlist ranked from AI spec evaluations, baseline scores, industry scanner, future release intelligence, and quantity guidance (research only — no purchases)."
        actions={
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void onRefreshLatest()}
            className="rounded-full border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {refreshing ? "Ranking…" : "Refresh Top 20"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {summary ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Active picks</p>
            <p className="mt-1 text-2xl font-semibold text-white">{summary.total_picks}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg final score</p>
            <p className={`mt-1 text-2xl font-semibold ${scoreClass(summary.average_final_score)}`}>
              {summary.average_final_score.toFixed(1)}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg confidence</p>
            <p className="mt-1 text-2xl font-semibold text-cyan-200">{summary.average_confidence_score.toFixed(3)}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Qty bridge</p>
            <p className="mt-1 text-2xl font-semibold text-white">{summary.with_suggested_quantity}</p>
          </div>
        </div>
      ) : null}

      <div className="mt-8 overflow-x-auto rounded-xl border border-white/10 bg-slate-900/40">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-3">Rank</th>
              <th className="px-3 py-3">Comic</th>
              <th className="px-3 py-3">Publisher</th>
              <th className="px-3 py-3">FOC</th>
              <th className="px-3 py-3">Release Date</th>
              <th className="px-3 py-3">Final Score</th>
              <th className="px-3 py-3">Confidence</th>
              <th className="px-3 py-3">Risk</th>
              <th className="px-3 py-3">Suggested Qty</th>
              <th className="min-w-[14rem] px-3 py-3">Rationale</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-slate-500">
                  Loading Top 20 picks…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-slate-500">
                  No Top 20 list yet. Refresh to rank spec candidates.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-3 py-3 font-semibold text-white">#{row.rank}</td>
                  <td className="px-3 py-3">
                    <p className="font-medium text-white">{row.title || `#${row.issue_number}`}</p>
                    <p className="text-xs text-slate-500">{row.issue_number}</p>
                  </td>
                  <td className="px-3 py-3 text-slate-300">{row.publisher || "—"}</td>
                  <td className="px-3 py-3 text-slate-400">{row.foc_date ?? "—"}</td>
                  <td className="px-3 py-3 text-slate-400">{row.release_date ?? "—"}</td>
                  <td className={`px-3 py-3 font-semibold ${scoreClass(row.final_score)}`}>{row.final_score.toFixed(1)}</td>
                  <td className="px-3 py-3 text-cyan-200">{row.confidence_score.toFixed(3)}</td>
                  <td className={`px-3 py-3 font-medium ${riskClass(row.risk_level)}`}>{row.risk_level}</td>
                  <td className="px-3 py-3 text-slate-300">{row.suggested_quantity ?? "—"}</td>
                  <td className="max-w-xs px-3 py-3 text-xs text-slate-400">{row.rationale}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
