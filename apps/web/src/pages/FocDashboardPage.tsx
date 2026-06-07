import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type FocDashboardItemRead,
  type FocDashboardRead,
  type PullListDecisionType,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { ContextualPageLinks } from "../components/ContextualPageLinks";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const DECISION_FILTERS: { label: string; value: PullListDecisionType | "" }[] = [
  { label: "All decisions", value: "" },
  { label: "Start Run", value: "START_RUN" },
  { label: "Continue Run", value: "CONTINUE_RUN" },
  { label: "Watch", value: "WATCH" },
  { label: "Pass", value: "PASS" },
];

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function StatCard({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

function formatReasons(reasons: string[]): string {
  if (!reasons.length) return "—";
  return reasons.join("; ");
}

function formatDecision(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace(/_/g, " ");
}

function DataTable({
  columns,
  rows,
  empty,
}: {
  columns: string[];
  rows: ReactNode[][];
  empty: string;
}): JSX.Element {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-600">{empty}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm text-slate-800">
        <thead>
          <tr className="border-b border-white/10 text-[11px] uppercase tracking-[0.12em] text-slate-500">
            {columns.map((col) => (
              <th key={col} className="px-2 py-2 font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, idx) => (
            <tr key={idx} className="border-b border-slate-100">
              {cells.map((cell, cellIdx) => (
                <td key={cellIdx} className="px-2 py-2 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function actionRows(items: FocDashboardItemRead[]): ReactNode[][] {
  return items.map((row) => [
    row.series_name || "—",
    row.issue_number || "—",
    formatDecision(row.decision_type),
    formatDate(row.foc_date),
    row.days_until_foc != null ? String(row.days_until_foc) : "—",
    formatReasons(row.reasons),
  ]);
}

function releaseRows(items: FocDashboardItemRead[]): ReactNode[][] {
  return items.map((row) => [
    row.series_name || "—",
    row.issue_number || "—",
    formatDate(row.release_date),
    formatDecision(row.decision_type),
  ]);
}

function watchRows(items: FocDashboardItemRead[]): ReactNode[][] {
  return items.map((row) => [row.series_name || "—", row.issue_number || "—", formatReasons(row.reasons)]);
}

export function FocDashboardPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<FocDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decisionFilter, setDecisionFilter] = useState<PullListDecisionType | "">("");
  const [publisherFilter, setPublisherFilter] = useState("");
  const [maxDaysFoc, setMaxDaysFoc] = useState("");
  const [maxDaysRelease, setMaxDaysRelease] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params: {
          decision_type?: string;
          publisher?: string;
          max_days_until_foc?: number;
          max_days_until_release?: number;
        } = {};
        if (decisionFilter) params.decision_type = decisionFilter;
        if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
        const focDays = maxDaysFoc.trim() ? Number(maxDaysFoc) : undefined;
        const relDays = maxDaysRelease.trim() ? Number(maxDaysRelease) : undefined;
        if (focDays != null && !Number.isNaN(focDays)) params.max_days_until_foc = focDays;
        if (relDays != null && !Number.isNaN(relDays)) params.max_days_until_release = relDays;
        const body = await apiClient.getFocDashboard(Object.keys(params).length ? params : undefined);
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load FOC dashboard.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [decisionFilter, publisherFilter, maxDaysFoc, maxDaysRelease]);

  const summary = dashboard?.summary;
  const actionRequired = useMemo(() => dashboard?.action_required ?? [], [dashboard]);
  const upcomingReleases = useMemo(() => dashboard?.upcoming_releases ?? [], [dashboard]);
  const watchlist = useMemo(() => dashboard?.watchlist ?? [], [dashboard]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P52-03"
        title="FOC Dashboard"
        description="Upcoming FOC deadlines and pull-list actions for your weekly preorder workflow (read-only)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <ContextualPageLinks links={[{ label: "Release Intelligence", to: "/release-intelligence" }]} />
      <div className="mt-4 flex flex-wrap gap-3">
        <select
          value={decisionFilter}
          onChange={(e) => setDecisionFilter(e.target.value as PullListDecisionType | "")}
          className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-200"
        >
          {DECISION_FILTERS.map((f) => (
            <option key={f.label} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Publisher filter"
          value={publisherFilter}
          onChange={(e) => setPublisherFilter(e.target.value)}
          className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-200"
        />
        <input
          type="number"
          min={0}
          placeholder="Max days to FOC"
          value={maxDaysFoc}
          onChange={(e) => setMaxDaysFoc(e.target.value)}
          className="w-36 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-200"
        />
        <input
          type="number"
          min={0}
          placeholder="Release window (days)"
          value={maxDaysRelease}
          onChange={(e) => setMaxDaysRelease(e.target.value)}
          className="w-44 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-200"
        />
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading FOC dashboard…</p>
      ) : (
        <div className="mt-6 space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Action Required" value={summary?.action_required_count ?? 0} />
            <StatCard label="Upcoming FOC" value={summary?.upcoming_foc_count ?? 0} />
            <StatCard label="Upcoming Releases" value={summary?.upcoming_release_count ?? 0} />
            <StatCard label="Watchlist" value={summary?.watch_count ?? 0} />
          </div>
          <Panel title="Action Required">
            <DataTable
              columns={["Series", "Issue", "Decision", "FOC Date", "Days Remaining", "Reason"]}
              rows={actionRows(actionRequired)}
              empty="No FOC actions in the next 14 days."
            />
          </Panel>
          <Panel title="Upcoming Releases">
            <DataTable
              columns={["Series", "Issue", "Release Date", "Decision"]}
              rows={releaseRows(upcomingReleases)}
              empty="No releases in the next 30 days."
            />
          </Panel>
          <Panel title="Watchlist">
            <DataTable
              columns={["Series", "Issue", "Reason"]}
              rows={watchRows(watchlist)}
              empty="No WATCH decisions on your catalog."
            />
          </Panel>
        </div>
      )}
    </AppShell>
  );
}
