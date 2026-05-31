import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type DailyActionSummaryRead,
  type DailyCollectorActionRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const ACTION_TYPES = ["", "PREORDER", "ACQUIRE", "GRADE", "SELL", "REBALANCE", "REVIEW", "WATCH"] as const;

export function DailyActionPage(): JSX.Element {
  const [items, setItems] = useState<DailyCollectorActionRead[]>([]);
  const [summary, setSummary] = useState<DailyActionSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [priorityMin, setPriorityMin] = useState("");
  const [dueBefore, setDueBefore] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { action_type?: string; priority_min?: number; due_before?: string } = {};
      if (typeFilter.trim()) params.action_type = typeFilter.trim();
      const pmin = Number(priorityMin);
      if (!Number.isNaN(pmin) && priorityMin.trim()) params.priority_min = pmin;
      if (dueBefore.trim()) params.due_before = dueBefore.trim();
      const [list, sum] = await Promise.all([apiClient.getDailyActions(params), apiClient.getDailyActionsSummary()]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load daily actions.");
    } finally {
      setLoading(false);
    }
  }, [dueBefore, priorityMin, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P57-02"
        title="Daily Actions"
        description="Actionable daily tasks from unified collector intelligence with FOC due dates and stable priority ordering."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {summary ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-4 lg:grid-cols-8">
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Total</p>
            <p className="text-lg font-semibold text-white">{summary.total_actions}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Critical</p>
            <p className="text-lg font-semibold text-white">{summary.critical_actions}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Preorder</p>
            <p className="text-lg font-semibold text-white">{summary.preorder_actions}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Acquire</p>
            <p className="text-lg font-semibold text-white">{summary.acquisition_actions}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Grade</p>
            <p className="text-lg font-semibold text-white">{summary.grading_actions}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Sell</p>
            <p className="text-lg font-semibold text-white">{summary.sell_actions}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Rebalance</p>
            <p className="text-lg font-semibold text-white">{summary.rebalance_actions}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
            <p className="text-slate-500">Watch</p>
            <p className="text-lg font-semibold text-white">{summary.watch_actions}</p>
          </div>
        </div>
      ) : null}
      <div className="mb-4 flex flex-wrap gap-3">
        <label className="text-sm text-slate-400">
          Action{" "}
          <select
            className="ml-1 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            {ACTION_TYPES.map((t) => (
              <option key={t || "all"} value={t}>
                {t || "All"}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-400">
          Priority min{" "}
          <input
            className="ml-1 w-20 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={priorityMin}
            onChange={(e) => setPriorityMin(e.target.value)}
          />
        </label>
        <label className="text-sm text-slate-400">
          Due before{" "}
          <input
            type="date"
            className="ml-1 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-white"
            value={dueBefore}
            onChange={(e) => setDueBefore(e.target.value)}
          />
        </label>
        <button type="button" className="rounded-lg bg-cyan-700 px-3 py-1 text-sm text-white" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">No daily actions yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-white/10">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Due Date</th>
                <th className="px-3 py-2">Sources</th>
                <th className="px-3 py-2">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-t border-white/5">
                  <td className="px-3 py-2 text-cyan-200">{row.action_type}</td>
                  <td className="px-3 py-2 font-medium text-white">{row.title}</td>
                  <td className="px-3 py-2">{row.priority_score.toFixed(1)}</td>
                  <td className="px-3 py-2">{row.confidence_score.toFixed(2)}</td>
                  <td className="px-3 py-2">{row.due_date ?? "—"}</td>
                  <td className="px-3 py-2 text-xs text-slate-400">{row.source_systems.join(", ")}</td>
                  <td className="px-3 py-2 text-slate-300">{row.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
