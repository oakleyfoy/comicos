import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type SpecBaselineScoreRead,
  type SpecBaselineScoreSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function scoreClass(score: number): string {
  if (score >= 70) return "text-emerald-300";
  if (score >= 45) return "text-cyan-200";
  return "text-slate-400";
}

function riskClass(score: number): string {
  if (score <= 35) return "text-emerald-300";
  if (score <= 60) return "text-amber-200";
  return "text-rose-300";
}

export function SpecBaselinePage(): JSX.Element {
  const [items, setItems] = useState<SpecBaselineScoreRead[]>([]);
  const [summary, setSummary] = useState<SpecBaselineScoreSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum] = await Promise.all([
        apiClient.getSpecBaselineScores(),
        apiClient.getSpecBaselineSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load spec baseline scores.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRegenerate() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const latest = await apiClient.getLatestSpecBaselineScores();
      setItems(latest.items);
      const sum = await apiClient.getSpecBaselineSummary();
      setSummary(sum);
      setMessage(
        `Computed ${latest.scores_computed}, updated ${latest.scores_updated}, skipped ${latest.scores_skipped} unchanged.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to regenerate baseline scores.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P60-02"
        title="Spec Baseline"
        description="Deterministic, explainable baseline spec scores from normalized inputs — non-AI comparison layer before Top 20 ranking."
        actions={
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void onRegenerate()}
            className="rounded-full border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {refreshing ? "Scoring…" : "Regenerate baseline"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {summary ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Scores</p>
            <p className="mt-1 text-2xl font-semibold text-white">{summary.total_scores}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg baseline</p>
            <p className={`mt-1 text-2xl font-semibold ${scoreClass(summary.average_baseline_score)}`}>
              {summary.average_baseline_score.toFixed(1)}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg confidence</p>
            <p className="mt-1 text-2xl font-semibold text-cyan-200">
              {summary.average_confidence_score.toFixed(3)}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg risk</p>
            <p className={`mt-1 text-2xl font-semibold ${riskClass(summary.average_risk_score)}`}>
              {summary.average_risk_score.toFixed(1)}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">High baseline (≥70)</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-300">{summary.high_baseline_count}</p>
          </div>
        </div>
      ) : null}

      <div className="mt-8 overflow-x-auto rounded-xl border border-white/10 bg-slate-900/40">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Release</th>
              <th className="px-4 py-3">Baseline</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Risk</th>
              <th className="px-4 py-3">Rationale</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  Loading baseline scores…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No baseline scores yet. Regenerate to score spec inputs.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{row.title || `${row.series_name} #${row.issue_number}`}</p>
                    <p className="text-xs text-slate-500">{row.publisher || "—"}</p>
                  </td>
                  <td className={`px-4 py-3 font-semibold ${scoreClass(row.baseline_score)}`}>
                    {row.baseline_score.toFixed(1)}
                  </td>
                  <td className="px-4 py-3 text-cyan-200">{row.confidence_score.toFixed(3)}</td>
                  <td className={`px-4 py-3 font-medium ${riskClass(row.risk_score)}`}>{row.risk_score.toFixed(1)}</td>
                  <td className="max-w-md px-4 py-3 text-xs text-slate-400">{row.rationale}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
