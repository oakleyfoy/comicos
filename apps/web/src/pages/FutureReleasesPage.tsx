import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type FutureReleaseMatchRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export function FutureReleasesPage(): JSX.Element {
  const [items, setItems] = useState<FutureReleaseMatchRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await apiClient.getFutureReleaseMatches();
      setItems(list.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load future release matches.");
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
      const list = await apiClient.refreshFutureReleaseMatches();
      setItems(list.items);
      setMessage(`Matched ${list.total_items} future Lunar release(s).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh future release matches.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P58-03"
        title="Future Releases"
        description="Next issues matched to upcoming Lunar catalog releases (FOC and ship dates)."
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
          {refreshing ? "Matching…" : "Match future releases"}
        </button>
      </div>

      <div className="mt-8 overflow-x-auto rounded-xl border border-white/10">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Series</th>
              <th className="px-4 py-3 font-medium">Issue</th>
              <th className="px-4 py-3 font-medium">FOC</th>
              <th className="px-4 py-3 font-medium">Release</th>
              <th className="px-4 py-3 font-medium">Variants</th>
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
                  No future matches yet. Detect next issues and import Lunar releases.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 font-medium text-white">{row.series_name}</td>
                  <td className="px-4 py-3 text-slate-200">#{row.issue_number}</td>
                  <td className="px-4 py-3 text-slate-300">{formatDate(row.foc_date)}</td>
                  <td className="px-4 py-3 text-slate-300">{formatDate(row.release_date)}</td>
                  <td className="px-4 py-3 text-slate-200">{row.variant_count}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
