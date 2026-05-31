import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type CrossSystemRecommendationRead,
  type CrossSystemRecommendationSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const REC_TYPES = ["", "PREORDER", "ACQUIRE", "GRADE", "SELL", "REBALANCE", "WATCH"] as const;

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function CrossSystemRecommendationPage(): JSX.Element {
  const [items, setItems] = useState<CrossSystemRecommendationRead[]>([]);
  const [summary, setSummary] = useState<CrossSystemRecommendationSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [rankMax, setRankMax] = useState("");
  const [priorityMin, setPriorityMin] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { recommendation_type?: string; rank_max?: number; priority_min?: number } = {};
      if (typeFilter.trim()) params.recommendation_type = typeFilter.trim();
      const rmax = Number(rankMax);
      if (!Number.isNaN(rmax) && rankMax.trim()) params.rank_max = rmax;
      const pmin = Number(priorityMin);
      if (!Number.isNaN(pmin) && priorityMin.trim()) params.priority_min = pmin;
      const [list, sum] = await Promise.all([
        apiClient.getCrossSystemRecommendations(params),
        apiClient.getCrossSystemRecommendationsSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load cross-system recommendations.");
    } finally {
      setLoading(false);
    }
  }, [priorityMin, rankMax, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P57-03"
        title="Cross-System Recommendations"
        description="Ranked, conflict-resolved actions across unified, purchase, portfolio, acquisition, and exit intelligence."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {summary ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Total</p>
            <p className="text-lg font-semibold text-white">{summary.total_recommendations}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Top acquire</p>
            <p className="text-lg font-semibold text-white">{summary.top_acquisitions}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Top preorder</p>
            <p className="text-lg font-semibold text-white">{summary.top_preorders}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Top grade</p>
            <p className="text-lg font-semibold text-white">{summary.top_grading_opportunities}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Top sell</p>
            <p className="text-lg font-semibold text-white">{summary.top_sell_opportunities}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Top rebalance</p>
            <p className="text-lg font-semibold text-white">{summary.top_rebalance_opportunities}</p>
          </div>
        </div>
      ) : null}
      <div className="mb-4 flex flex-wrap gap-3">
        <label className="text-sm text-slate-400">
          Type{" "}
          <select
            className="ml-1 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            {REC_TYPES.map((t) => (
              <option key={t || "all"} value={t}>
                {t || "All"}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-400">
          Rank max{" "}
          <input
            className="ml-1 w-16 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={rankMax}
            onChange={(e) => setRankMax(e.target.value)}
          />
        </label>
        <label className="text-sm text-slate-400">
          Priority min{" "}
          <input
            className="ml-1 w-20 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={priorityMin}
            onChange={(e) => setPriorityMin(e.target.value)}
          />
        </label>
        <button type="button" className="rounded-lg bg-cyan-700 px-3 py-1 text-sm text-white" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">No cross-system recommendations yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-white/10">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-3 py-2">Rank</th>
                <th className="px-3 py-2">Recommendation</th>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Sources</th>
                <th className="px-3 py-2">Est. value</th>
                <th className="px-3 py-2">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-t border-white/5">
                  <td className="px-3 py-2">{row.recommendation_rank}</td>
                  <td className="px-3 py-2 text-cyan-200">{row.recommendation_type}</td>
                  <td className="px-3 py-2 font-medium text-white">{row.title}</td>
                  <td className="px-3 py-2">{row.priority_score.toFixed(1)}</td>
                  <td className="px-3 py-2">{row.confidence_score.toFixed(2)}</td>
                  <td className="px-3 py-2 text-xs text-slate-400">{row.source_systems.join(", ")}</td>
                  <td className="px-3 py-2">{money(row.estimated_value)}</td>
                  <td className="px-3 py-2 text-slate-300">{row.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
