import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type AcquisitionOpportunityRead,
  type AcquisitionOpportunitySummaryRead,
  type AcquisitionOpportunityType,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const TYPE_FILTERS: { label: string; value: AcquisitionOpportunityType | "" }[] = [
  { label: "All types", value: "" },
  { label: "Collection gap", value: "COLLECTION_GAP" },
  { label: "Want list item", value: "WANT_LIST_ITEM" },
  { label: "Key target", value: "KEY_TARGET" },
  { label: "Milestone target", value: "MILESTONE_TARGET" },
  { label: "Run completion", value: "RUN_COMPLETION_TARGET" },
];

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function AcquisitionOpportunityPage(): JSX.Element {
  const [items, setItems] = useState<AcquisitionOpportunityRead[]>([]);
  const [summary, setSummary] = useState<AcquisitionOpportunitySummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<AcquisitionOpportunityType | "">("");
  const [priorityMin, setPriorityMin] = useState("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { opportunity_type?: string; priority_score_min?: number; publisher?: string } = {};
      if (typeFilter) params.opportunity_type = typeFilter;
      const min = Number(priorityMin);
      if (!Number.isNaN(min) && priorityMin.trim()) params.priority_score_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const [list, sum] = await Promise.all([
        apiClient.getAcquisitionOpportunities(params),
        apiClient.getAcquisitionOpportunitySummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load acquisition opportunities.");
    } finally {
      setLoading(false);
    }
  }, [priorityMin, publisherFilter, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const params: { opportunity_type?: string; priority_score_min?: number; publisher?: string } = {};
      if (typeFilter) params.opportunity_type = typeFilter;
      const min = Number(priorityMin);
      if (!Number.isNaN(min) && priorityMin.trim()) params.priority_score_min = min;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const list = await apiClient.refreshAcquisitionOpportunities(params);
      setItems(list.items);
      const sum = await apiClient.getAcquisitionOpportunitySummary();
      setSummary(sum);
      setMessage(`Generated opportunities (${list.total_items} active).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh opportunities.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P55-03"
        title="Acquisition Opportunities"
        description="Deal and gap-based acquisition scoring from want lists and collection gaps (no marketplace search or purchases)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Opportunity type
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as AcquisitionOpportunityType | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {TYPE_FILTERS.map((o) => (
              <option key={o.label} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Min priority score
          <input
            type="number"
            min={0}
            max={100}
            value={priorityMin}
            onChange={(e) => setPriorityMin(e.target.value)}
            className="mt-1 block w-28 rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          />
        </label>
        <label className="text-xs text-slate-400">
          Publisher
          <input
            type="text"
            value={publisherFilter}
            onChange={(e) => setPublisherFilter(e.target.value)}
            className="mt-1 block w-40 rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          />
        </label>
        <button
          type="button"
          disabled={refreshing}
          onClick={() => void onRefresh()}
          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 disabled:opacity-50"
        >
          Generate opportunities
        </button>
      </div>

      {summary ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase text-slate-500">Active opportunities</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.total_opportunities}</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase text-slate-500">Avg priority score</p>
            <p className="mt-2 text-2xl font-semibold text-cyan-100">{summary.average_priority_score.toFixed(1)}</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase text-slate-500">With target price</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-200">{summary.with_target_price}</p>
          </div>
        </div>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">No opportunities yet. Add gaps or want-list targets and generate.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Comic</th>
                <th className="px-4 py-3">Opportunity type</th>
                <th className="px-4 py-3">Priority score</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Target price</th>
                <th className="px-4 py-3">Value gap</th>
                <th className="px-4 py-3">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-slate-100">
                  <td className="px-4 py-3 text-white">
                    {row.publisher ? `${row.publisher} · ` : ""}
                    {row.series_name} #{row.issue_number}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{row.opportunity_type.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 font-medium text-cyan-100">{row.priority_score.toFixed(1)}</td>
                  <td className="px-4 py-3 text-slate-600">{(row.confidence_score * 100).toFixed(0)}%</td>
                  <td className="px-4 py-3 text-slate-800">{money(row.target_price)}</td>
                  <td className="px-4 py-3 text-emerald-200">{money(row.value_gap)}</td>
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
