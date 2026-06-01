import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiClient, type IndustryReleaseSignalRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const SIGNAL_FILTERS = [
  "",
  "NUMBER_ONE",
  "FIRST_APPEARANCE",
  "RATIO_VARIANT",
  "FACSIMILE",
  "ANNIVERSARY",
  "KEY_EVENT",
  "NEW_SERIES",
  "ONE_SHOT",
  "CROSSOVER",
  "MILESTONE",
  "UNKNOWN",
] as const;

function confidenceClass(score: number): string {
  if (score >= 0.85) return "text-emerald-300";
  if (score >= 0.6) return "text-cyan-200";
  return "text-slate-400";
}

export function IndustrySignalsPage(): JSX.Element {
  const [items, setItems] = useState<IndustryReleaseSignalRead[]>([]);
  const [scanRunId, setScanRunId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [signalFilter, setSignalFilter] = useState<string>("");

  const loadList = useCallback(async (filter: string) => {
    setError(null);
    const params: { signal_type?: string } = {};
    if (filter) params.signal_type = filter;
    const list = await apiClient.getIndustryReleaseSignals(params);
    setItems(list.items);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await loadList(signalFilter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load industry signals.");
    } finally {
      setLoading(false);
    }
  }, [loadList, signalFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefreshLatest() {
    setRefreshing(true);
    setMessage(null);
    setError(null);
    try {
      const latest = await apiClient.refreshIndustryReleaseSignals();
      setScanRunId(latest.scan_run_id);
      setMessage(`Classified ${latest.signals_classified} signal(s) for scan run ${latest.scan_run_id ?? "—"}.`);
      setItems(latest.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh latest signals.");
    } finally {
      setRefreshing(false);
    }
  }

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of items) {
      counts.set(row.signal_type, (counts.get(row.signal_type) ?? 0) + 1);
    }
    return counts;
  }, [items]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P59-03"
        title="Industry Signals"
        description="Rule-based collectible/spec signal classification for industry release candidates (no AI scoring or Top 20 ranking)."
        actions={
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void onRefreshLatest()}
            className="rounded-full border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {refreshing ? "Classifying…" : "Refresh latest"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {scanRunId ? (
        <p className="mt-4 text-xs text-slate-500">Latest classification scan run ID: {scanRunId}</p>
      ) : null}

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Signal type
          <select
            className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-xs text-slate-200"
            value={signalFilter}
            onChange={(e) => setSignalFilter(e.target.value)}
          >
            {SIGNAL_FILTERS.map((value) => (
              <option key={value || "all"} value={value}>
                {value || "All types"}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 hover:border-white/20"
          onClick={() => void load()}
        >
          Apply filter
        </button>
      </div>

      {!loading && items.length > 0 ? (
        <div className="mt-6 flex flex-wrap gap-2">
          {[...typeCounts.entries()].map(([type, count]) => (
            <span key={type} className="rounded-full border border-white/10 bg-slate-900/60 px-2 py-1 text-xs text-slate-300">
              {type}: {count}
            </span>
          ))}
        </div>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading industry signals…</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-white/10">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Publisher</th>
                <th className="px-4 py-3">Series</th>
                <th className="px-4 py-3">Issue</th>
                <th className="px-4 py-3">Signal</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-slate-500">
                    No signals yet — run an industry release scan, then refresh latest classifications.
                  </td>
                </tr>
              ) : (
                items.map((row) => (
                  <tr key={row.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 text-slate-300">{row.publisher_name}</td>
                    <td className="px-4 py-3 text-white">{row.series_name}</td>
                    <td className="px-4 py-3 text-slate-400">#{row.issue_number}</td>
                    <td className="px-4 py-3 font-medium text-cyan-100">{row.signal_type}</td>
                    <td className={`px-4 py-3 ${confidenceClass(row.confidence_score)}`}>
                      {row.confidence_score.toFixed(2)}
                    </td>
                    <td className="max-w-md px-4 py-3 text-xs text-slate-400">{row.rationale}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
