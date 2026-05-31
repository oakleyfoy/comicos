import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type UnifiedCollectorRecommendationRead,
  type UnifiedCollectorSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const REC_TYPES = ["", "PREORDER", "ACQUIRE", "GRADE", "SELL", "REBALANCE", "WATCH"] as const;
const SOURCE_SYSTEMS = [
  "",
  "P52_PULL_LIST",
  "P53_PURCHASE",
  "P54_PORTFOLIO",
  "P55_ACQUISITION",
  "P56_EXIT",
] as const;

export function UnifiedCollectorPage(): JSX.Element {
  const [items, setItems] = useState<UnifiedCollectorRecommendationRead[]>([]);
  const [summary, setSummary] = useState<UnifiedCollectorSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [priorityMin, setPriorityMin] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { recommendation_type?: string; source_system?: string; priority_min?: number } = {};
      if (typeFilter.trim()) params.recommendation_type = typeFilter.trim();
      if (sourceFilter.trim()) params.source_system = sourceFilter.trim();
      const min = Number(priorityMin);
      if (!Number.isNaN(min) && priorityMin.trim()) params.priority_min = min;
      const [list, sum] = await Promise.all([apiClient.getUnifiedIntelligence(params), apiClient.getUnifiedIntelligenceSummary()]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load unified intelligence.");
    } finally {
      setLoading(false);
    }
  }, [priorityMin, sourceFilter, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Collector Intelligence"
        title="Unified Intelligence"
        description="Cross-system collector recommendations from pull list, purchase, portfolio, acquisition, and exit intelligence."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {summary ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Total</p>
            <p className="text-lg font-semibold text-white">{summary.total_recommendations}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Acquire</p>
            <p className="text-lg font-semibold text-white">{summary.acquire_count}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Sell</p>
            <p className="text-lg font-semibold text-white">{summary.sell_count}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Multi-source</p>
            <p className="text-lg font-semibold text-white">{summary.multi_source_count}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Avg priority</p>
            <p className="text-lg font-semibold text-white">{summary.average_priority.toFixed(1)}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Avg confidence</p>
            <p className="text-lg font-semibold text-white">{summary.average_confidence.toFixed(2)}</p>
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
          Source{" "}
          <select
            className="ml-1 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
          >
            {SOURCE_SYSTEMS.map((s) => (
              <option key={s || "all"} value={s}>
                {s || "All"}
              </option>
            ))}
          </select>
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
        <p className="text-sm text-slate-500">No unified recommendations yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-white/10">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Sources</th>
                <th className="px-3 py-2">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-t border-white/5">
                  <td className="px-3 py-2 text-cyan-200">{row.recommendation_type}</td>
                  <td className="px-3 py-2 font-medium text-white">{row.title}</td>
                  <td className="px-3 py-2">{row.priority_score.toFixed(1)}</td>
                  <td className="px-3 py-2">{row.confidence_score.toFixed(2)}</td>
                  <td className="px-3 py-2 text-xs text-slate-400">{row.source_systems.join(", ")}</td>
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
