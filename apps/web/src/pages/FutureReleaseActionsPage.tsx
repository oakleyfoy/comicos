import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type FutureReleaseActionRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { futureReleaseActionBadge, lightTable } from "../lib/lightSurfaceUi";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export function FutureReleaseActionsPage(): JSX.Element {
  const [items, setItems] = useState<FutureReleaseActionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await apiClient.getFutureReleaseActions();
      setItems(list.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load future release actions.");
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
      const list = await apiClient.refreshFutureReleaseActions();
      setItems(list.items);
      setMessage(`Generated ${list.total_items} preorder action(s).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh future release actions.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P58-04"
        title="Future Release Actions"
        description="Preorder intelligence from future Lunar matches — FOC-driven actions and priority scores."
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
          {refreshing ? "Generating…" : "Generate actions"}
        </button>
      </div>

      <div className="mt-8 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className={lightTable}>
          <thead className="border-b border-slate-200 bg-slate-800 text-xs uppercase tracking-wide text-slate-200">
            <tr>
              <th className="px-4 py-3 font-medium">Series</th>
              <th className="px-4 py-3 font-medium">Issue</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Priority</th>
              <th className="px-4 py-3 font-medium">FOC</th>
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
                  No actions yet. Match future releases first, then generate actions.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{row.series_name}</td>
                  <td className="px-4 py-3 text-slate-800">#{row.issue_number}</td>
                  <td className="px-4 py-3">
                    <span className={futureReleaseActionBadge(row.action_type)}>{row.action_type}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-800">{row.priority_score.toFixed(1)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatDate(row.foc_date)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
