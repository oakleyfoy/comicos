import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type GradeBeforeSellAction,
  type GradeBeforeSellRecommendationRead,
  type GradeBeforeSellSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const REC_FILTERS: { label: string; value: GradeBeforeSellAction | "" }[] = [
  { label: "All recommendations", value: "" },
  { label: "Grade before sell", value: "GRADE_BEFORE_SELL" },
  { label: "Sell raw", value: "SELL_RAW" },
  { label: "Hold for review", value: "HOLD_FOR_REVIEW" },
];

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function recClass(rec: GradeBeforeSellAction): string {
  if (rec === "GRADE_BEFORE_SELL") return "text-emerald-300";
  if (rec === "SELL_RAW") return "text-rose-300";
  return "text-amber-200";
}

export function GradeBeforeSellPage(): JSX.Element {
  const [items, setItems] = useState<GradeBeforeSellRecommendationRead[]>([]);
  const [summary, setSummary] = useState<GradeBeforeSellSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [recFilter, setRecFilter] = useState<GradeBeforeSellAction | "">("");
  const [roiMin, setRoiMin] = useState("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { recommendation?: string; roi_min?: number; publisher?: string } = {};
      if (recFilter) params.recommendation = recFilter;
      const min = Number(roiMin);
      if (!Number.isNaN(min) && roiMin.trim()) params.roi_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const [list, sum] = await Promise.all([
        apiClient.getGradeBeforeSellRecommendations(params),
        apiClient.getGradeBeforeSellSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load grade before sell recommendations.");
    } finally {
      setLoading(false);
    }
  }, [publisherFilter, recFilter, roiMin]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const params: { recommendation?: string; roi_min?: number; publisher?: string } = {};
      if (recFilter) params.recommendation = recFilter;
      const min = Number(roiMin);
      if (!Number.isNaN(min) && roiMin.trim()) params.roi_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const list = await apiClient.refreshGradeBeforeSellRecommendations(params);
      setItems(list.items);
      const sum = await apiClient.getGradeBeforeSellSummary();
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
        eyebrow="P56-03"
        title="Grade Before Sell"
        description="Grade vs sell-raw guidance from grading upside, costs, and hold/sell context (no submissions or sales)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {summary ? (
        <p className="mt-4 text-sm text-slate-400">
          {summary.grade_before_sell_count} grade · {summary.sell_raw_count} sell raw · {summary.hold_for_review_count} review · avg ROI{" "}
          {summary.average_expected_roi.toFixed(2)}
        </p>
      ) : null}
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Recommendation
          <select
            value={recFilter}
            onChange={(e) => setRecFilter(e.target.value as GradeBeforeSellAction | "")}
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
          Min ROI
          <input
            value={roiMin}
            onChange={(e) => setRoiMin(e.target.value)}
            placeholder="e.g. 1.0"
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
        <p className="mt-6 text-sm text-slate-400">No recommendations yet. Add inventory and grading candidates, then run generation.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Comic</th>
                <th className="px-4 py-3">Recommendation</th>
                <th className="px-4 py-3">Current Value</th>
                <th className="px-4 py-3">Expected Graded</th>
                <th className="px-4 py-3">Grading Cost</th>
                <th className="px-4 py-3">Value Gain</th>
                <th className="px-4 py-3">ROI</th>
                <th className="px-4 py-3">Confidence</th>
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
                  <td className={`px-4 py-3 font-semibold ${recClass(row.recommendation)}`}>
                    {row.recommendation.replace(/_/g, " ")}
                  </td>
                  <td className="px-4 py-3">{money(row.current_estimated_value)}</td>
                  <td className="px-4 py-3">{money(row.expected_graded_value)}</td>
                  <td className="px-4 py-3">{money(row.estimated_grading_cost)}</td>
                  <td className="px-4 py-3">{money(row.expected_value_gain)}</td>
                  <td className="px-4 py-3">{row.expected_roi.toFixed(2)}</td>
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
