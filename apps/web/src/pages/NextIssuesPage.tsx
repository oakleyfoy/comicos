import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type NextIssueRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function confidenceClass(value: number): string {
  if (value >= 1.0) return "text-emerald-300";
  if (value >= 0.75) return "text-cyan-200";
  return "text-slate-400";
}

export function NextIssuesPage(): JSX.Element {
  const [items, setItems] = useState<NextIssueRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await apiClient.getNextIssues();
      setItems(list.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load next issues.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const list = await apiClient.refreshNextIssues();
      setItems(list.items);
      setMessage(`Refreshed next issues (${list.total_items} series).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh next issues.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P58-02"
        title="Next Issues"
        description="Next sequential issue for each collected run, matched against your Lunar release catalog (read-only)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      <div className="mt-6">
        <button
          type="button"
          onClick={() => void onRefresh()}
          disabled={refreshing}
          className="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          {refreshing ? "Detecting…" : "Detect next issues"}
        </button>
      </div>

      <div className="mt-8 overflow-x-auto rounded-xl border border-white/10">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Series</th>
              <th className="px-4 py-3 font-medium">Current issue</th>
              <th className="px-4 py-3 font-medium">Next issue</th>
              <th className="px-4 py-3 font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                  No next issues yet. Refresh collected runs and import Lunar releases.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 font-medium text-white">{row.series_name}</td>
                  <td className="px-4 py-3 text-slate-200">#{row.current_issue}</td>
                  <td className="px-4 py-3 text-slate-200">#{row.next_issue}</td>
                  <td className={`px-4 py-3 font-medium ${confidenceClass(row.confidence)}`}>
                    {row.confidence.toFixed(2)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
