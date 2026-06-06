import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type CollectionGapPriority,
  type CollectionGapRead,
  type CollectionGapSummaryRead,
  type CollectionGapType,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const PRIORITY_FILTERS: { label: string; value: CollectionGapPriority | "" }[] = [
  { label: "All priorities", value: "" },
  { label: "Critical", value: "CRITICAL" },
  { label: "High", value: "HIGH" },
  { label: "Medium", value: "MEDIUM" },
  { label: "Low", value: "LOW" },
];

const GAP_TYPE_FILTERS: { label: string; value: CollectionGapType | "" }[] = [
  { label: "All gap types", value: "" },
  { label: "Missing issue", value: "MISSING_ISSUE" },
  { label: "Run gap", value: "RUN_GAP" },
  { label: "Key missing", value: "KEY_MISSING" },
  { label: "Milestone missing", value: "MILESTONE_MISSING" },
];

function priorityClass(p: CollectionGapPriority): string {
  if (p === "CRITICAL") return "text-rose-800";
  if (p === "HIGH") return "text-amber-800";
  if (p === "MEDIUM") return "text-cyan-200";
  return "text-slate-400";
}

export function CollectionGapPage(): JSX.Element {
  const [items, setItems] = useState<CollectionGapRead[]>([]);
  const [summary, setSummary] = useState<CollectionGapSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<CollectionGapPriority | "">("");
  const [gapTypeFilter, setGapTypeFilter] = useState<CollectionGapType | "">("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { priority?: string; gap_type?: string; publisher?: string } = {};
      if (priorityFilter) params.priority = priorityFilter;
      if (gapTypeFilter) params.gap_type = gapTypeFilter;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const [list, sum] = await Promise.all([
        apiClient.getCollectionGaps(params),
        apiClient.getCollectionGapSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load collection gaps.");
    } finally {
      setLoading(false);
    }
  }, [gapTypeFilter, priorityFilter, publisherFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefreshGaps() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const params: { priority?: string; gap_type?: string; publisher?: string } = {};
      if (priorityFilter) params.priority = priorityFilter;
      if (gapTypeFilter) params.gap_type = gapTypeFilter;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const list = await apiClient.refreshCollectionGaps(params);
      setItems(list.items);
      const sum = await apiClient.getCollectionGapSummary();
      setSummary(sum);
      setMessage(`Refreshed gaps (${list.total_items} active).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh collection gaps.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P55-02"
        title="Collection Gaps"
        description="Missing issues and incomplete runs from inventory and run completeness (advisory — no marketplace search or purchases)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Priority
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value as CollectionGapPriority | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {PRIORITY_FILTERS.map((o) => (
              <option key={o.label} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Gap type
          <select
            value={gapTypeFilter}
            onChange={(e) => setGapTypeFilter(e.target.value as CollectionGapType | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {GAP_TYPE_FILTERS.map((o) => (
              <option key={o.label} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
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
          onClick={() => void onRefreshGaps()}
          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 disabled:opacity-50"
        >
          Generate gaps
        </button>
      </div>

      {summary ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase text-slate-500">Active gaps</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.total_gaps}</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase text-slate-500">Avg completion</p>
            <p className="mt-2 text-2xl font-semibold text-cyan-100">{summary.average_completion_percent.toFixed(1)}%</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase text-slate-500">Critical</p>
            <p className="mt-2 text-2xl font-semibold text-rose-200">{summary.by_priority.CRITICAL ?? 0}</p>
          </div>
        </div>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">No collection gaps yet. Add inventory runs and generate gaps.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Series</th>
                <th className="px-4 py-3">Missing issue</th>
                <th className="px-4 py-3">Gap type</th>
                <th className="px-4 py-3">Completion %</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-slate-100">
                  <td className="px-4 py-3 text-white">
                    {row.publisher ? `${row.publisher} · ` : ""}
                    {row.series_name}
                  </td>
                  <td className="px-4 py-3 text-slate-800">{row.issue_number || "—"}</td>
                  <td className="px-4 py-3 text-slate-600">{row.gap_type.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 text-slate-800">{row.completion_percent.toFixed(1)}%</td>
                  <td className={`px-4 py-3 font-medium ${priorityClass(row.priority)}`}>{row.priority}</td>
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
