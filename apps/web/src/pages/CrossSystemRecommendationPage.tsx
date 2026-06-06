import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type CrossSystemRecommendationRead,
  type CrossSystemRecommendationSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { PrintingBadge } from "../components/PrintingBadge";
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
  const [rebuilding, setRebuilding] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [rebuildError, setRebuildError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [rankMax, setRankMax] = useState("");
  const [priorityMin, setPriorityMin] = useState("");

  const buildParams = useCallback(() => {
    const params: { recommendation_type?: string; rank_max?: number; priority_min?: number } = {};
    if (typeFilter.trim()) params.recommendation_type = typeFilter.trim();
    const rmax = Number(rankMax);
    if (!Number.isNaN(rmax) && rankMax.trim()) params.rank_max = rmax;
    const pmin = Number(priorityMin);
    if (!Number.isNaN(pmin) && priorityMin.trim()) params.priority_min = pmin;
    return params;
  }, [priorityMin, rankMax, typeFilter]);

  const load = useCallback(async () => {
    setLoading(true);
    setListError(null);
    setSummaryError(null);
    const params = buildParams();

    const listPromise = apiClient.getCrossSystemRecommendations(params);
    const summaryPromise = apiClient.getCrossSystemRecommendationsSummary();

    try {
      const list = await listPromise;
      setItems(list.items);
    } catch (err) {
      setItems([]);
      setListError(err instanceof ApiError ? err.message : "Unable to load cross-system recommendations.");
    }

    try {
      const sum = await summaryPromise;
      setSummary(sum);
    } catch (err) {
      setSummary(null);
      setSummaryError(err instanceof ApiError ? err.message : "Unable to load recommendation summary.");
    }

    setLoading(false);
  }, [buildParams]);

  const rebuild = useCallback(async () => {
    setRebuilding(true);
    setRebuildError(null);
    try {
      await apiClient.rebuildCrossSystemRecommendations();
      await load();
    } catch (err) {
      setRebuildError(err instanceof ApiError ? err.message : "Rebuild failed.");
    } finally {
      setRebuilding(false);
    }
  }, [load]);

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
      {listError ? <StatusBanner tone="error">{listError}</StatusBanner> : null}
      {summaryError ? (
        <StatusBanner tone="warning">Summary unavailable: {summaryError}</StatusBanner>
      ) : null}
      {rebuildError ? <StatusBanner tone="error">{rebuildError}</StatusBanner> : null}
      {summary?.readiness_status === "NOT_READY" && summary.readiness_reason ? (
        <StatusBanner tone="warning">{summary.readiness_reason}</StatusBanner>
      ) : null}
      {summary && summary.readiness_status !== "NOT_READY" ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Total</p>
            <p className="text-lg font-semibold text-slate-900">{summary.total_recommendations}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top acquire</p>
            <p className="text-lg font-semibold text-slate-900">{summary.top_acquisitions}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top preorder</p>
            <p className="text-lg font-semibold text-slate-900">{summary.top_preorders}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top grade</p>
            <p className="text-lg font-semibold text-slate-900">{summary.top_grading_opportunities}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top sell</p>
            <p className="text-lg font-semibold text-slate-900">{summary.top_sell_opportunities}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
            <p className="text-white/70">Top rebalance</p>
            <p className="text-lg font-semibold text-slate-900">{summary.top_rebalance_opportunities}</p>
          </div>
        </div>
      ) : null}
      <div className="mb-4 flex flex-wrap gap-3">
        <label className="text-sm text-slate-600">
          Type{" "}
          <select
            className="ml-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900"
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
        <label className="text-sm text-slate-600">
          Rank max{" "}
          <input
            className="ml-1 w-16 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={rankMax}
            onChange={(e) => setRankMax(e.target.value)}
          />
        </label>
        <label className="text-sm text-slate-600">
          Priority min{" "}
          <input
            className="ml-1 w-20 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={priorityMin}
            onChange={(e) => setPriorityMin(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="rounded-lg border border-slate-600 px-3 py-1 text-sm text-white"
          disabled={loading}
          onClick={() => void load()}
        >
          Reload
        </button>
        <button
          type="button"
          className="rounded-lg bg-cyan-700 px-3 py-1 text-sm text-white disabled:opacity-60"
          disabled={rebuilding || loading}
          onClick={() => void rebuild()}
        >
          {rebuilding ? "Rebuilding…" : "Refresh rankings"}
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : !listError && items.length === 0 ? (
        <p className="text-sm text-slate-500">No cross-system recommendations yet. Use Refresh rankings to rebuild.</p>
      ) : items.length === 0 ? null : (
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
                  <h2 className="flex flex-wrap items-center gap-2 text-lg font-semibold text-white">
                    <span>{row.title}</span>
                    <PrintingBadge badge={row.decision?.printing_badge} />
                  </h2>
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
                      <span className="font-medium text-slate-900">Sources:</span>{" "}
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
