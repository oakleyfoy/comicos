import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type SpecInputRead,
  type SpecInputSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function systemsLabel(systems: string[]): string {
  return systems.length ? systems.join(", ") : "—";
}

export function SpecInputsPage(): JSX.Element {
  const [items, setItems] = useState<SpecInputRead[]>([]);
  const [summary, setSummary] = useState<SpecInputSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum] = await Promise.all([apiClient.getSpecInputs(), apiClient.getSpecInputSummary()]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load spec inputs.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRebuildLatest() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const latest = await apiClient.getLatestSpecInputs();
      setItems(latest.items);
      const sum = await apiClient.getSpecInputSummary();
      setSummary(sum);
      setMessage(
        `Built ${latest.inputs_created} new, updated ${latest.inputs_updated}, skipped ${latest.inputs_skipped} unchanged.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to rebuild spec inputs.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P60-01"
        title="Spec Inputs"
        description="Normalized evaluation dataset bridging Release Intelligence, Future Release, Industry Scanner, purchase profile, and pull list signals (foundation for AI Spec Engine — not Top 20 ranking)."
        actions={
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void onRebuildLatest()}
            className="rounded-full border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {refreshing ? "Building…" : "Rebuild inputs"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {summary ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Total inputs</p>
            <p className="mt-1 text-2xl font-semibold text-white">{summary.total_inputs}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Unique releases</p>
            <p className="mt-1 text-2xl font-semibold text-white">{summary.unique_releases}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Industry linked</p>
            <p className="mt-1 text-2xl font-semibold text-cyan-200">{summary.with_industry_candidate}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Future match linked</p>
            <p className="mt-1 text-2xl font-semibold text-cyan-200">{summary.with_future_match}</p>
          </div>
        </div>
      ) : null}

      <div className="mt-8 overflow-x-auto rounded-xl border border-white/10 bg-slate-900/40">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Release</th>
              <th className="px-4 py-3">Publisher</th>
              <th className="px-4 py-3">FOC</th>
              <th className="px-4 py-3">Source systems</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  Loading spec inputs…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  No spec inputs yet. Rebuild to materialize the evaluation dataset.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{row.title || `${row.series_name} #${row.issue_number}`}</p>
                    <p className="text-xs text-slate-500">Release #{row.release_id ?? "—"}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-300">{row.publisher || "—"}</td>
                  <td className="px-4 py-3 text-slate-400">{row.foc_date ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-cyan-100/90">{systemsLabel(row.source_systems)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
