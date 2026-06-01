import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type IndustryOpportunityRead,
  type IndustryOpportunitySummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function riskClass(level: string): string {
  if (level === "LOW") return "text-emerald-300";
  if (level === "MEDIUM") return "text-amber-200";
  return "text-rose-300";
}

function scoreClass(score: number): string {
  if (score >= 70) return "text-emerald-300";
  if (score >= 45) return "text-cyan-200";
  return "text-slate-400";
}

export function IndustryOpportunitiesPage(): JSX.Element {
  const [items, setItems] = useState<IndustryOpportunityRead[]>([]);
  const [summary, setSummary] = useState<IndustryOpportunitySummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum] = await Promise.all([
        apiClient.getIndustryOpportunities(),
        apiClient.getIndustryOpportunitySummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load industry opportunities.");
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
      const latest = await apiClient.refreshIndustryOpportunities();
      setItems(latest.items);
      const sum = await apiClient.getIndustryOpportunitySummary();
      setSummary(sum);
      setMessage(`Scored ${latest.scores_computed} opportunit${latest.scores_computed === 1 ? "y" : "ies"}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh opportunity scores.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P59-04"
        title="Industry Opportunities"
        description="Signal-weighted industry release opportunity scores with publisher-aware weighting and risk flags (not a Top 20 preorder list)."
        actions={
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void onRefreshLatest()}
            className="rounded-full border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {refreshing ? "Scoring…" : "Refresh scores"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {summary ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Opportunities</p>
            <p className="mt-1 text-2xl font-semibold text-white">{summary.total_opportunities}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg score</p>
            <p className={`mt-1 text-2xl font-semibold ${scoreClass(summary.average_opportunity_score)}`}>
              {summary.average_opportunity_score.toFixed(1)}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">High (≥70)</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-300">{summary.high_opportunity_count}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Low risk</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-300">{summary.low_risk_count}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">High risk</p>
            <p className="mt-1 text-2xl font-semibold text-rose-300">{summary.high_risk_count}</p>
          </div>
        </div>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading industry opportunities…</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-white/10">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Publisher</th>
                <th className="px-4 py-3">Series</th>
                <th className="px-4 py-3">Issue</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-slate-500">
                    No scores yet — run an industry release scan and refresh scores.
                  </td>
                </tr>
              ) : (
                items.map((row) => (
                  <tr key={row.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                    <td className={`px-4 py-3 text-lg font-semibold ${scoreClass(row.opportunity_score)}`}>
                      {row.opportunity_score.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-slate-300">{row.publisher_name}</td>
                    <td className="px-4 py-3 text-white">{row.series_name}</td>
                    <td className="px-4 py-3 text-slate-400">#{row.issue_number}</td>
                    <td className="px-4 py-3 text-cyan-200">{row.confidence_score.toFixed(2)}</td>
                    <td className={`px-4 py-3 font-medium ${riskClass(row.risk_level)}`}>{row.risk_level}</td>
                    <td className="max-w-lg px-4 py-3 text-xs text-slate-400">{row.rationale}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
