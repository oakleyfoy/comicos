import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type ExitDashboardItemRead, type ExitDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function SectionTable({
  title,
  items,
  empty,
}: {
  title: string;
  items: ExitDashboardItemRead[];
  empty: string;
}): JSX.Element {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/65 p-4">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">{empty}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={`${item.item_type}-${item.item_id}`} className="rounded-xl border border-white/5 bg-slate-950/50 px-3 py-2 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium text-white">{item.title}</span>
                {item.recommendation ? (
                  <span className="text-cyan-200">{item.recommendation.replace(/_/g, " ")}</span>
                ) : item.action ? (
                  <span className="text-amber-200">{item.action.replace(/_/g, " ")}</span>
                ) : null}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {item.publisher ? `${item.publisher} · ` : ""}
                {item.priority_score != null ? `Score ${item.priority_score.toFixed(1)} · ` : ""}
                {item.confidence_score != null ? `Conf ${item.confidence_score.toFixed(2)} · ` : ""}
                {item.capital_value != null ? `Capital ${money(item.capital_value)}` : ""}
              </p>
              {item.rationale ? <p className="mt-1 text-xs text-slate-400">{item.rationale}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ExitDashboardPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ExitDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [publisherFilter, setPublisherFilter] = useState("");
  const [recommendationFilter, setRecommendationFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [scoreMin, setScoreMin] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { publisher?: string; recommendation?: string; action?: string; score_min?: number } = {};
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      if (recommendationFilter.trim()) params.recommendation = recommendationFilter.trim();
      if (actionFilter.trim()) params.action = actionFilter.trim();
      const min = Number(scoreMin);
      if (!Number.isNaN(min) && scoreMin.trim()) params.score_min = min;
      const body = await apiClient.getExitDashboard(params);
      setDashboard(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load exit dashboard.");
    } finally {
      setLoading(false);
    }
  }, [actionFilter, publisherFilter, recommendationFilter, scoreMin]);

  useEffect(() => {
    void load();
  }, [load]);

  const s = dashboard?.summary;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P56-05"
        title="Exit Dashboard"
        description="Daily view of sell, grade-before-sell, rebalancing, capital recovery, and review items (read-only aggregation)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <div className="mt-4 flex flex-wrap gap-3">
        <input
          placeholder="Publisher filter"
          value={publisherFilter}
          onChange={(e) => setPublisherFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5 text-sm text-white"
        />
        <input
          placeholder="Recommendation filter"
          value={recommendationFilter}
          onChange={(e) => setRecommendationFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5 text-sm text-white"
        />
        <input
          placeholder="Action filter"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5 text-sm text-white"
        />
        <input
          placeholder="Min score"
          value={scoreMin}
          onChange={(e) => setScoreMin(e.target.value)}
          className="w-24 rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5 text-sm text-white"
        />
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : s && dashboard ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Exit candidates</p>
              <p className="mt-1 text-2xl font-semibold text-white">{s.total_exit_candidates}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Sell recs</p>
              <p className="mt-1 text-2xl font-semibold text-rose-200">{s.sell_recommendations}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Grade before sell</p>
              <p className="mt-1 text-2xl font-semibold text-emerald-200">{s.grade_before_sell_recommendations}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Rebalance actions</p>
              <p className="mt-1 text-2xl font-semibold text-amber-200">{s.rebalance_actions}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Capital recovery</p>
              <p className="mt-1 text-2xl font-semibold text-cyan-200">{money(s.estimated_capital_recovery)}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Review required</p>
              <p className="mt-1 text-2xl font-semibold text-white">{s.review_required_count}</p>
            </div>
          </div>
          <div className="mt-8 grid gap-4 lg:grid-cols-2">
            <SectionTable title="Top sell recommendations" items={dashboard.top_sell_recommendations} empty="No SELL recommendations." />
            <SectionTable title="Grade before sell opportunities" items={dashboard.top_grade_before_sell} empty="No grade-before-sell opportunities." />
            <SectionTable title="Portfolio rebalance actions" items={dashboard.top_rebalance_actions} empty="No rebalance actions." />
            <SectionTable title="Capital recovery" items={dashboard.capital_recovery} empty="No capital recovery items." />
            <SectionTable title="Review required" items={dashboard.review_required} empty="Nothing flagged for review." />
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
