import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type CrossSystemRecommendationRead,
  type CrossSystemRecommendationSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { RecommendationDecisionPanel } from "../components/RecommendationDecisionPanel";
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
        title="Top Recommendations"
        description="Ranked cross-system picks with purchase decisions — quantity, cover, risk, strategy, and FOC timing."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {summary ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Total</p>
            <p className="text-lg font-semibold text-white">{summary.total_recommendations}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top acquire</p>
            <p className="text-lg font-semibold text-white">{summary.top_acquisitions}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top preorder</p>
            <p className="text-lg font-semibold text-white">{summary.top_preorders}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top grade</p>
            <p className="text-lg font-semibold text-white">{summary.top_grading_opportunities}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top sell</p>
            <p className="text-lg font-semibold text-white">{summary.top_sell_opportunities}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top rebalance</p>
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
        <ul className="space-y-4">
          {items.map((row) => (
            <li
              key={row.id}
              className="rounded-2xl border border-slate-700 bg-slate-900 p-4 text-white shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-white/75">
                    #{row.recommendation_rank} · {row.recommendation_type}
                  </p>
                  <h2 className="text-lg font-semibold text-white">{row.title}</h2>
                </div>
                <div className="text-right text-xs text-white/90">
                  <p>Priority {row.priority_score.toFixed(1)}</p>
                  <p>Confidence {row.confidence_score.toFixed(2)}</p>
                  <p>{money(row.estimated_value)}</p>
                </div>
              </div>
              {row.decision ? <RecommendationDecisionPanel decision={row.decision} /> : null}
              {(row.source_systems.length > 0 || row.rationale) && (
                <div
                  className={
                    row.source_systems.length > 0
                      ? "mt-3 grid gap-3 sm:grid-cols-2 sm:items-start"
                      : "mt-3"
                  }
                >
                  {row.source_systems.length > 0 ? (
                    <p className="text-xs leading-relaxed text-white/90">
                      <span className="font-medium text-white">Sources:</span>{" "}
                      {row.source_systems.join(", ")}
                    </p>
                  ) : null}
                  {row.rationale ? (
                    <p className="text-sm leading-relaxed text-white">{row.rationale}</p>
                  ) : null}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
