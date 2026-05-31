import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type HoldSellAction,
  type HoldSellRecommendationRead,
  type HoldSellSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const REC_FILTERS: { label: string; value: HoldSellAction | "" }[] = [
  { label: "All recommendations", value: "" },
  { label: "Sell", value: "SELL" },
  { label: "Watch", value: "WATCH" },
  { label: "Hold", value: "HOLD" },
];

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function recClass(rec: HoldSellAction): string {
  if (rec === "SELL") return "text-rose-300";
  if (rec === "WATCH") return "text-amber-200";
  return "text-slate-300";
}

export function HoldSellPage(): JSX.Element {
  const [items, setItems] = useState<HoldSellRecommendationRead[]>([]);
  const [summary, setSummary] = useState<HoldSellSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [recFilter, setRecFilter] = useState<HoldSellAction | "">("");
  const [convictionMin, setConvictionMin] = useState("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { recommendation?: string; conviction_min?: number; publisher?: string } = {};
      if (recFilter) params.recommendation = recFilter;
      const min = Number(convictionMin);
      if (!Number.isNaN(min) && convictionMin.trim()) params.conviction_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const [list, sum] = await Promise.all([
        apiClient.getHoldSellRecommendations(params),
        apiClient.getHoldSellSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load hold vs sell recommendations.");
    } finally {
      setLoading(false);
    }
  }, [convictionMin, publisherFilter, recFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const params: { recommendation?: string; conviction_min?: number; publisher?: string } = {};
      if (recFilter) params.recommendation = recFilter;
      const min = Number(convictionMin);
      if (!Number.isNaN(min) && convictionMin.trim()) params.conviction_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const list = await apiClient.refreshHoldSellRecommendations(params);
      setItems(list.items);
      const sum = await apiClient.getHoldSellSummary();
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
        eyebrow="P56-02"
        title="Hold vs Sell"
        description="Exit timing guidance from profit, exposure, grading status, and portfolio signals (no listings, sales, or grading advice)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {summary ? (
        <p className="mt-4 text-sm text-slate-400">
          {summary.sell_count} sell · {summary.watch_count} watch · {summary.hold_count} hold · avg conviction{" "}
          {summary.average_conviction.toFixed(1)}
        </p>
      ) : null}
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Recommendation
          <select
            value={recFilter}
            onChange={(e) => setRecFilter(e.target.value as HoldSellAction | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {REC_FILTERS.map((f) => (
              <option key={f.label} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Min conviction
          <input
            value={convictionMin}
            onChange={(e) => setConvictionMin(e.target.value)}
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
        <p className="mt-6 text-sm text-slate-400">No recommendations yet. Add inventory and run generation.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Comic</th>
                <th className="px-4 py-3">Recommendation</th>
                <th className="px-4 py-3">Conviction</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">FMV</th>
                <th className="px-4 py-3">Cost</th>
                <th className="px-4 py-3">Unrealized Gain</th>
                <th className="px-4 py-3">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 text-slate-200">
                  <td className="px-4 py-3">
                    <div className="font-medium text-white">
                      {row.title} #{row.issue_number}
                    </div>
                    <div className="text-xs text-slate-500">{row.publisher}</div>
                  </td>
                  <td className={`px-4 py-3 font-semibold ${recClass(row.recommendation)}`}>{row.recommendation}</td>
                  <td className="px-4 py-3">{row.conviction_score.toFixed(1)}</td>
                  <td className="px-4 py-3">{row.confidence_score.toFixed(2)}</td>
                  <td className="px-4 py-3">{money(row.estimated_fmv)}</td>
                  <td className="px-4 py-3">{money(row.acquisition_cost)}</td>
                  <td className="px-4 py-3">{money(row.unrealized_gain)}</td>
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
