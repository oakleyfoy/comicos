import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type ExitCandidateRead,
  type ExitCandidateReason,
  type ExitCandidateSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const REASON_FILTERS: { label: string; value: ExitCandidateReason | "" }[] = [
  { label: "All reasons", value: "" },
  { label: "Duplicate", value: "DUPLICATE" },
  { label: "Profitable", value: "PROFITABLE" },
  { label: "Graded", value: "GRADED" },
  { label: "Overexposed", value: "OVEREXPOSED" },
  { label: "Capital recovery", value: "CAPITAL_RECOVERY" },
  { label: "Multiple signals", value: "MULTIPLE_SIGNALS" },
];

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function ExitCandidatePage(): JSX.Element {
  const [items, setItems] = useState<ExitCandidateRead[]>([]);
  const [summary, setSummary] = useState<ExitCandidateSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reasonFilter, setReasonFilter] = useState<ExitCandidateReason | "">("");
  const [scoreMin, setScoreMin] = useState("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { candidate_reason?: string; score_min?: number; publisher?: string } = {};
      if (reasonFilter) params.candidate_reason = reasonFilter;
      const min = Number(scoreMin);
      if (!Number.isNaN(min) && scoreMin.trim()) params.score_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const [list, sum] = await Promise.all([apiClient.getExitCandidates(params), apiClient.getExitCandidateSummary()]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load exit candidates.");
    } finally {
      setLoading(false);
    }
  }, [publisherFilter, reasonFilter, scoreMin]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const params: { candidate_reason?: string; score_min?: number; publisher?: string } = {};
      if (reasonFilter) params.candidate_reason = reasonFilter;
      const min = Number(scoreMin);
      if (!Number.isNaN(min) && scoreMin.trim()) params.score_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const list = await apiClient.refreshExitCandidates(params);
      setItems(list.items);
      const sum = await apiClient.getExitCandidateSummary();
      setSummary(sum);
      setMessage(`Refreshed exit candidates (${list.total_items} active).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh exit candidates.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P56-01"
        title="Exit Candidates"
        description="Disposition signals from duplicates, profit, grading, and portfolio exposure (no hold/sell decisions or sales)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {summary ? (
        <p className="mt-4 text-sm text-slate-400">
          {summary.total_candidates} candidate(s) · avg score {summary.average_candidate_score.toFixed(1)} · total unrealized gain{" "}
          {money(summary.total_unrealized_gain)}
        </p>
      ) : null}
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Reason
          <select
            value={reasonFilter}
            onChange={(e) => setReasonFilter(e.target.value as ExitCandidateReason | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {REASON_FILTERS.map((f) => (
              <option key={f.label} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Min score
          <input
            value={scoreMin}
            onChange={(e) => setScoreMin(e.target.value)}
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
          Generate exit candidates
        </button>
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">No exit candidates yet. Add inventory and run generation.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Comic</th>
                <th className="px-4 py-3">Candidate Score</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">FMV</th>
                <th className="px-4 py-3">Cost</th>
                <th className="px-4 py-3">Unrealized Gain</th>
                <th className="px-4 py-3">Reason</th>
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
                  <td className="px-4 py-3 font-semibold text-cyan-200">{row.candidate_score.toFixed(1)}</td>
                  <td className="px-4 py-3">{row.confidence_score.toFixed(2)}</td>
                  <td className="px-4 py-3">{money(row.estimated_fmv)}</td>
                  <td className="px-4 py-3">{money(row.acquisition_cost)}</td>
                  <td className="px-4 py-3">{money(row.unrealized_gain)}</td>
                  <td className="px-4 py-3 text-amber-100">{row.candidate_reason.replace(/_/g, " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
