import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type PortfolioRebalanceAction,
  type PortfolioRebalanceRecommendationRead,
  type PortfolioRebalanceSummaryRead,
  type PortfolioRebalanceType,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const TYPE_FILTERS: { label: string; value: PortfolioRebalanceType | "" }[] = [
  { label: "All types", value: "" },
  { label: "Title overexposure", value: "TITLE_OVEREXPOSURE" },
  { label: "Publisher overexposure", value: "PUBLISHER_OVEREXPOSURE" },
  { label: "Character overexposure", value: "CHARACTER_OVEREXPOSURE" },
  { label: "Modern / spec", value: "MODERN_SPEC_OVEREXPOSURE" },
  { label: "Duplicate capital", value: "DUPLICATE_CAPITAL" },
  { label: "Low efficiency capital", value: "LOW_EFFICIENCY_CAPITAL" },
];

const ACTION_FILTERS: { label: string; value: PortfolioRebalanceAction | "" }[] = [
  { label: "All actions", value: "" },
  { label: "Reduce exposure", value: "REDUCE_EXPOSURE" },
  { label: "Review position", value: "REVIEW_POSITION" },
  { label: "Hold", value: "HOLD" },
];

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function PortfolioRebalancingPage(): JSX.Element {
  const [items, setItems] = useState<PortfolioRebalanceRecommendationRead[]>([]);
  const [summary, setSummary] = useState<PortfolioRebalanceSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<PortfolioRebalanceType | "">("");
  const [actionFilter, setActionFilter] = useState<PortfolioRebalanceAction | "">("");
  const [priorityMin, setPriorityMin] = useState("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: {
        rebalance_type?: string;
        recommended_action?: string;
        priority_min?: number;
        publisher?: string;
      } = {};
      if (typeFilter) params.rebalance_type = typeFilter;
      if (actionFilter) params.recommended_action = actionFilter;
      const min = Number(priorityMin);
      if (!Number.isNaN(min) && priorityMin.trim()) params.priority_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const [list, sum] = await Promise.all([
        apiClient.getPortfolioRebalancingRecommendations(params),
        apiClient.getPortfolioRebalancingSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load portfolio rebalancing recommendations.");
    } finally {
      setLoading(false);
    }
  }, [actionFilter, priorityMin, publisherFilter, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const params: {
        rebalance_type?: string;
        recommended_action?: string;
        priority_min?: number;
        publisher?: string;
      } = {};
      if (typeFilter) params.rebalance_type = typeFilter;
      if (actionFilter) params.recommended_action = actionFilter;
      const min = Number(priorityMin);
      if (!Number.isNaN(min) && priorityMin.trim()) params.priority_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const list = await apiClient.refreshPortfolioRebalancingRecommendations(params);
      setItems(list.items);
      const sum = await apiClient.getPortfolioRebalancingSummary();
      setSummary(sum);
      setMessage(`Generated recommendations (${list.total_items} active).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to generate recommendations.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P56-04"
        title="Portfolio Rebalancing"
        description="Concentration, duplicate capital, and efficiency signals (no listings, sales, or rebalancing trades)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {summary ? (
        <p className="mt-4 text-sm text-slate-400">
          {summary.reduce_exposure_count} reduce · {summary.review_position_count} review · avg priority{" "}
          {summary.average_priority_score.toFixed(1)}
        </p>
      ) : null}
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Type
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as PortfolioRebalanceType | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {TYPE_FILTERS.map((f) => (
              <option key={f.label} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Action
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value as PortfolioRebalanceAction | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {ACTION_FILTERS.map((f) => (
              <option key={f.label} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Min priority
          <input
            value={priorityMin}
            onChange={(e) => setPriorityMin(e.target.value)}
            placeholder="0–100"
            className="mt-1 block w-24 rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          />
        </label>
        <label className="text-xs text-slate-400">
          Publisher
          <input
            value={publisherFilter}
            onChange={(e) => setPublisherFilter(e.target.value)}
            placeholder="Filter publisher"
            className="mt-1 block w-40 rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          />
        </label>
        <button
          type="button"
          disabled={refreshing}
          onClick={() => void onRefresh()}
          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 disabled:opacity-50"
        >
          Generate recommendations
        </button>
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">No rebalancing recommendations yet. Build inventory and run generation.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3">Rebalance Type</th>
                <th className="px-4 py-3">Exposure %</th>
                <th className="px-4 py-3">Exposure Value</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 text-slate-200">
                  <td className="px-4 py-3">
                    <div className="font-medium text-white">{row.target_label}</div>
                    {row.publisher ? <div className="text-xs text-slate-500">{row.publisher}</div> : null}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{row.rebalance_type.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3">{row.exposure_percent.toFixed(1)}%</td>
                  <td className="px-4 py-3">{money(row.exposure_value)}</td>
                  <td className="px-4 py-3 text-amber-100">{row.recommended_action.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3">{row.priority_score.toFixed(1)}</td>
                  <td className="px-4 py-3">{row.confidence_score.toFixed(2)}</td>
                  <td className="max-w-md px-4 py-3 text-slate-400">{row.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
