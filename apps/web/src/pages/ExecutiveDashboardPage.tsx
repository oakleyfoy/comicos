import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type ExecutiveDashboardItemRead,
  type ExecutiveDashboardRead,
  type ExecutiveDashboardSectionRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function SectionPanel({ block }: { block: ExecutiveDashboardSectionRead }): JSX.Element {
  return (
    <div className="rounded-2xl border border-blue-900/40 bg-patriot-navy p-4 text-white shadow-md">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-white">{block.title}</h3>
      {block.items.length === 0 ? (
        <p className="mt-3 text-sm text-white">{block.empty_message}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {block.items.map((item) => (
            <li
              key={`${block.section}-${item.item_type}-${item.item_id}`}
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-white [&_p]:text-white"
            >
              <ItemRow item={item} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ItemMetaLine({ item }: { item: ExecutiveDashboardItemRead }): JSX.Element | null {
  const parts: string[] = [];
  if (item.publisher) parts.push(item.publisher);
  if (item.recommendation_rank != null) parts.push(`Rank ${item.recommendation_rank}`);
  if (item.priority_score != null) parts.push(`Priority ${item.priority_score.toFixed(1)}`);
  if (item.confidence_score != null) parts.push(`Conf ${item.confidence_score.toFixed(2)}`);
  if (item.due_date) parts.push(`Due ${item.due_date}`);
  if (item.estimated_value != null) parts.push(`Est ${money(item.estimated_value)}`);
  if (parts.length === 0) return null;
  return <p className="mt-1 text-xs text-white">{parts.join(" · ")}</p>;
}

function ItemRow({ item }: { item: ExecutiveDashboardItemRead }): JSX.Element {
  const badge = item.action_type || item.recommendation_type || item.health_status;
  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-medium text-white">{item.title}</span>
        {badge ? (
          <span className="shrink-0 font-medium uppercase tracking-wide text-sky-200">{badge.replace(/_/g, " ")}</span>
        ) : null}
      </div>
      <ItemMetaLine item={item} />
      {item.source_systems.length > 0 ? (
        <p className="mt-1 text-xs text-white">Sources: {item.source_systems.join(", ")}</p>
      ) : null}
      {item.rationale ? <p className="mt-1 text-xs leading-relaxed text-white">{item.rationale}</p> : null}
    </>
  );
}

export function ExecutiveDashboardPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ExecutiveDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [priorityMin, setPriorityMin] = useState("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: {
        recommendation_type?: string;
        action_type?: string;
        priority_min?: number;
        publisher?: string;
      } = {};
      if (typeFilter.trim()) params.recommendation_type = typeFilter.trim();
      if (actionFilter.trim()) params.action_type = actionFilter.trim();
      const pmin = Number(priorityMin);
      if (!Number.isNaN(pmin) && priorityMin.trim()) params.priority_min = pmin;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const body = await apiClient.getExecutiveDashboard(params);
      setDashboard(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load executive dashboard.");
    } finally {
      setLoading(false);
    }
  }, [actionFilter, priorityMin, publisherFilter, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const s = dashboard?.summary;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P57-04"
        title="Executive Dashboard"
        description="ComicOS command center — daily actions, cross-system recommendations, acquisition, exit, and portfolio signals in one view."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <div className="mb-4 flex flex-wrap gap-2">
        <select
          className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        >
          <option value="">All action types</option>
          {["PREORDER", "ACQUIRE", "GRADE", "SELL", "REBALANCE", "WATCH", "REVIEW"].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">All recommendation types</option>
          {["PREORDER", "ACQUIRE", "GRADE", "SELL", "REBALANCE", "WATCH"].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          className="w-28 rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
          placeholder="Priority min"
          value={priorityMin}
          onChange={(e) => setPriorityMin(e.target.value)}
        />
        <input
          className="w-36 rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
          placeholder="Publisher"
          value={publisherFilter}
          onChange={(e) => setPublisherFilter(e.target.value)}
        />
        <button
          type="button"
          className="rounded-xl bg-patriot-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-900"
          onClick={() => void load()}
        >
          Refresh
        </button>
      </div>
      {s ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          <SummaryCard label="Daily Actions" value={s.total_daily_actions} />
          <SummaryCard label="Critical Actions" value={s.critical_daily_actions} />
          <SummaryCard label="Preorders" value={s.preorder_action_count} />
          <SummaryCard label="Acquisitions" value={s.acquisition_target_count} />
          <SummaryCard label="Grade Opportunities" value={s.grading_opportunity_count} />
          <SummaryCard label="Sell Opportunities" value={s.sell_opportunity_count} />
          <SummaryCard label="Capital Recovery" value={money(s.estimated_capital_recovery)} />
          <SummaryCard label="Budget Remaining" value={s.budget_remaining != null ? money(s.budget_remaining) : "—"} />
        </div>
      ) : null}
      {loading && !dashboard ? <p className="text-sm text-slate-600">Loading executive dashboard…</p> : null}
      {dashboard ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionPanel block={dashboard.daily_actions} />
          <SectionPanel block={dashboard.top_recommendations} />
          <SectionPanel block={dashboard.preorder_this_week} />
          <SectionPanel block={dashboard.acquire_targets} />
          <SectionPanel block={dashboard.grade_opportunities} />
          <SectionPanel block={dashboard.sell_opportunities} />
          <SectionPanel block={dashboard.portfolio_risk} />
          <SectionPanel block={dashboard.watch_items} />
          <div className="lg:col-span-2">
            <SectionPanel block={dashboard.system_health} />
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

function SummaryCard({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="rounded-xl border border-blue-900/40 bg-patriot-navy px-3 py-2 text-sm text-white shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-white">{label}</p>
      <p className="text-lg font-semibold text-white">{value}</p>
    </div>
  );
}
