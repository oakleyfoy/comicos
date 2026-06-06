import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type DailyActionSummaryRead,
  type DailyCollectorActionRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { PrintingBadge } from "../components/PrintingBadge";
import { RecommendationDecisionPanel } from "../components/RecommendationDecisionPanel";
import { StatusBanner } from "../components/StatusBanner";

const ACTION_TYPES = ["", "PREORDER", "ACQUIRE", "GRADE", "SELL", "REBALANCE", "REVIEW", "WATCH"] as const;

const ACTION_TYPE_BADGE: Record<string, string> = {
  PREORDER: "bg-sky-100 text-sky-900 ring-sky-200",
  ACQUIRE: "bg-emerald-100 text-emerald-900 ring-emerald-200",
  GRADE: "bg-violet-100 text-violet-900 ring-violet-200",
  SELL: "bg-amber-100 text-amber-950 ring-amber-200",
  REBALANCE: "bg-indigo-100 text-indigo-900 ring-indigo-200",
  REVIEW: "bg-slate-100 text-slate-800 ring-slate-200",
  WATCH: "bg-slate-100 text-slate-800 ring-slate-200",
};

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
        title="Today's Actions"
        description="Daily tasks with explicit buy/watch/pass decisions, copy counts, cover guidance, and FOC deadlines."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {summary ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-4 lg:grid-cols-8">
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
            <p className="text-slate-500">Total</p>
            <p className="text-lg font-semibold text-slate-900">{summary.total_actions}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
            <p className="text-slate-500">Critical</p>
            <p className="text-lg font-semibold text-slate-900">{summary.critical_actions}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
            <p className="text-slate-500">Preorder</p>
            <p className="text-lg font-semibold text-slate-900">{summary.preorder_actions}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
            <p className="text-slate-500">Acquire</p>
            <p className="text-lg font-semibold text-slate-900">{summary.acquisition_actions}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
            <p className="text-slate-500">Grade</p>
            <p className="text-lg font-semibold text-slate-900">{summary.grading_actions}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
            <p className="text-slate-500">Sell</p>
            <p className="text-lg font-semibold text-slate-900">{summary.sell_actions}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
            <p className="text-slate-500">Rebalance</p>
            <p className="text-lg font-semibold text-slate-900">{summary.rebalance_actions}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
            <p className="text-slate-500">Watch</p>
            <p className="text-lg font-semibold text-slate-900">{summary.watch_actions}</p>
          </div>
        </div>
      ) : null}
      <div className="mb-4 flex flex-wrap gap-3">
        <label className="text-sm text-slate-600">
          Action{" "}
          <select
            className="ml-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900"
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
        <label className="text-sm text-slate-600">
          Priority min{" "}
          <input
            className="ml-1 w-20 rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900"
            value={priorityMin}
            onChange={(e) => setPriorityMin(e.target.value)}
          />
        </label>
        <label className="text-sm text-slate-600">
          Due before{" "}
          <input
            type="date"
            className="ml-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900"
            value={dueBefore}
            onChange={(e) => setDueBefore(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="rounded-lg bg-blue-700 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-800"
          onClick={() => void load()}
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">No daily actions yet.</p>
      ) : (
        <ul className="space-y-4">
          {items.map((row) => {
            const badgeClass = ACTION_TYPE_BADGE[row.action_type] ?? "bg-slate-100 text-slate-800 ring-slate-200";
            return (
              <li key={row.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <span
                      className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${badgeClass}`}
                    >
                      {row.action_type}
                    </span>
                    <h2 className="mt-2 flex flex-wrap items-center gap-2 text-lg font-semibold text-slate-900">
                      <span>{row.title}</span>
                      <PrintingBadge
                        badge={row.decision?.printing_badge}
                        className="border-amber-500/50 bg-amber-50 text-amber-950"
                      />
                    </h2>
                  </div>
                  <dl className="shrink-0 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-right text-xs text-slate-700">
                    <div>
                      <dt className="inline text-slate-500">Priority </dt>
                      <dd className="inline font-semibold text-slate-900">{row.priority_score.toFixed(1)}</dd>
                    </div>
                    <div className="mt-0.5">
                      <dt className="inline text-slate-500">Confidence </dt>
                      <dd className="inline font-medium text-slate-800">{row.confidence_score.toFixed(2)}</dd>
                    </div>
                    {row.due_date ? (
                      <div className="mt-0.5">
                        <dt className="inline text-slate-500">Due </dt>
                        <dd className="inline font-medium text-slate-800">{row.due_date}</dd>
                      </div>
                    ) : null}
                  </dl>
                </div>
                {row.source_systems.length > 0 ? (
                  <p className="mt-2 text-xs font-medium text-slate-600">
                    Sources: <span className="font-normal text-slate-700">{row.source_systems.join(", ")}</span>
                  </p>
                ) : null}
                <p className="mt-2 text-sm leading-relaxed text-slate-700">{row.rationale}</p>
                {row.decision ? <RecommendationDecisionPanel decision={row.decision} /> : null}
              </li>
            );
          })}
        </ul>
      )}
    </AppShell>
  );
}
