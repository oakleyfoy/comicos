import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type AISpecEvaluationRead,
  type AISpecEvaluationSummaryRead,
} from "../api/client";
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
  if (level === "MEDIUM") return "text-amber-800";
  return "text-rose-800";
}

export function AISpecEvaluationsPage(): JSX.Element {
  const [items, setItems] = useState<AISpecEvaluationRead[]>([]);
  const [summary, setSummary] = useState<AISpecEvaluationSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum] = await Promise.all([
        apiClient.getAISpecEvaluations(),
        apiClient.getAISpecEvaluationSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load AI spec evaluations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRunLatest() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const latest = await apiClient.refreshAISpecEvaluations();
      setItems(latest.items);
      const sum = await apiClient.getAISpecEvaluationSummary();
      setSummary(sum);
      setMessage(
        `Evaluated ${latest.evaluations_computed} new, updated ${latest.evaluations_updated}, skipped ${latest.evaluations_skipped}; ${latest.fallback_count} fallback.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to run AI spec evaluations.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P60-03"
        title="AI Spec Evaluations"
        description="AI-assisted spec assessments layered on deterministic baseline scores — includes fallback when no AI provider is configured."
        actions={
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void onRunLatest()}
            className="rounded-full border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {refreshing ? "Evaluating…" : "Run evaluations"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {summary ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Evaluations</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{summary.total_evaluations}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg AI score</p>
            <p className={`mt-1 text-2xl font-semibold ${scoreClass(summary.average_ai_score)}`}>
              {summary.average_ai_score.toFixed(1)}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg confidence</p>
            <p className="mt-1 text-2xl font-semibold text-cyan-200">{summary.average_ai_confidence.toFixed(3)}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">AI success</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-300">{summary.success_count}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Fallback</p>
            <p className="mt-1 text-2xl font-semibold text-amber-800">{summary.fallback_count}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Risk mix</p>
            <p className="mt-1 text-xs text-slate-300">
              L {summary.low_risk_count} · M {summary.medium_risk_count} · H {summary.high_risk_count}
            </p>
          </div>
        </div>
      ) : null}

      <div className="mt-8 overflow-x-auto rounded-xl border border-white/10 bg-slate-900/40">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Release</th>
              <th className="px-4 py-3">AI score</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Risk</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Rationale</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  Loading AI evaluations…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No AI spec evaluations yet. Run evaluations to generate assessments.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{row.title || `${row.series_name} #${row.issue_number}`}</p>
                    <p className="text-xs text-slate-500">
                      {row.model_name} · {row.prompt_version}
                    </p>
                  </td>
                  <td className={`px-4 py-3 font-semibold ${scoreClass(row.ai_score)}`}>{row.ai_score.toFixed(1)}</td>
                  <td className="px-4 py-3 text-cyan-200">{row.ai_confidence.toFixed(3)}</td>
                  <td className={`px-4 py-3 font-medium ${riskClass(row.risk_level)}`}>{row.risk_level}</td>
                  <td className="px-4 py-3 text-xs text-slate-400">{row.evaluation_status}</td>
                  <td className="max-w-md px-4 py-3 text-xs text-slate-400">{row.ai_rationale}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
