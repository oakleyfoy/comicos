import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type CollectedRunRead,
  type CollectedRunStatus,
  type CollectedRunSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const STATUS_FILTERS: { label: string; value: CollectedRunStatus | "" }[] = [
  { label: "All statuses", value: "" },
  { label: "Active", value: "ACTIVE" },
  { label: "Inactive", value: "INACTIVE" },
  { label: "Complete", value: "COMPLETE" },
  { label: "Unknown", value: "UNKNOWN" },
];

function statusClass(status: CollectedRunStatus): string {
  if (status === "ACTIVE") return "text-emerald-300";
  if (status === "INACTIVE") return "text-slate-400";
  if (status === "COMPLETE") return "text-cyan-200";
  return "text-amber-800";
}

export function CollectedRunsPage(): JSX.Element {
  const [items, setItems] = useState<CollectedRunRead[]>([]);
  const [summary, setSummary] = useState<CollectedRunSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<CollectedRunStatus | "">("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { run_status?: string; publisher?: string } = {};
      if (statusFilter) params.run_status = statusFilter;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const [list, sum] = await Promise.all([
        apiClient.getCollectedRuns(params),
        apiClient.getCollectedRunSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load collected runs.");
    } finally {
      setLoading(false);
    }
  }, [publisherFilter, statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefreshRuns() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const params: { run_status?: string; publisher?: string } = {};
      if (statusFilter) params.run_status = statusFilter;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const list = await apiClient.refreshCollectedRuns(params);
      setItems(list.items);
      const sum = await apiClient.getCollectedRunSummary();
      setSummary(sum);
      setMessage(`Refreshed runs (${list.total_items} series).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh collected runs.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P58-01"
        title="Collected Runs"
        description="Ongoing series you are collecting, inferred from inventory and release intelligence (read-only — no alerts or inventory changes)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {summary ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Total runs</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{summary.total_runs}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Active</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-300">{summary.active_runs}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Inactive</p>
            <p className="mt-1 text-2xl font-semibold text-slate-300">{summary.inactive_runs}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Complete</p>
            <p className="mt-1 text-2xl font-semibold text-cyan-200">{summary.complete_runs}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Unknown</p>
            <p className="mt-1 text-2xl font-semibold text-amber-800">{summary.unknown_runs}</p>
          </div>
        </div>
      ) : null}

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Status
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as CollectedRunStatus | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {STATUS_FILTERS.map((o) => (
              <option key={o.label} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Publisher contains
          <input
            value={publisherFilter}
            onChange={(e) => setPublisherFilter(e.target.value)}
            className="mt-1 block w-40 rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
            placeholder="e.g. Image"
          />
        </label>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white hover:bg-slate-700 disabled:opacity-50"
        >
          Apply filters
        </button>
        <button
          type="button"
          onClick={() => void onRefreshRuns()}
          disabled={refreshing}
          className="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          {refreshing ? "Detecting…" : "Detect runs from inventory"}
        </button>
      </div>

      <div className="mt-8 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-800 text-xs uppercase tracking-wide text-slate-200">
            <tr>
              <th className="px-4 py-3 font-medium">Series</th>
              <th className="px-4 py-3 font-medium">Publisher</th>
              <th className="px-4 py-3 font-medium">Latest owned</th>
              <th className="px-4 py-3 font-medium">Count</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  No collected runs yet. Add inventory and run detection.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{row.series_name}</td>
                  <td className="px-4 py-3 text-slate-600">{row.publisher}</td>
                  <td className="px-4 py-3 text-slate-800">#{row.latest_owned_issue}</td>
                  <td className="px-4 py-3 text-slate-800">{row.total_owned_issues}</td>
                  <td className={`px-4 py-3 font-medium ${statusClass(row.run_status)}`}>{row.run_status}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
