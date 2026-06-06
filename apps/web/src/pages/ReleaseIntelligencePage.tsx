import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type ReleaseIntelligenceDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { VariantList } from "../components/VariantList";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function IssueList({
  items,
}: {
  items: { id: number; title: string; issue_number: string; release_date: string | null; foc_date: string | null }[];
}): JSX.Element {
  if (!items.length) return <p className="text-sm text-slate-500">No entries yet.</p>;
  return (
    <ul className="space-y-2 text-sm text-slate-300">
      {items.map((row) => (
        <li key={row.id} className="flex justify-between gap-3">
          <span>
            {row.title || "Untitled"} #{row.issue_number}
          </span>
          <span className="text-slate-400">{row.release_date ?? row.foc_date ?? "TBD"}</span>
        </li>
      ))}
    </ul>
  );
}

function SignalList({
  items,
}: {
  items: { signal: { id: number; signal_type: string }; issue: { title: string; issue_number: string }; series: { series_name: string } }[];
}): JSX.Element {
  if (!items.length) return <p className="text-sm text-slate-500">No signals yet.</p>;
  return (
    <ul className="space-y-2 text-sm text-slate-300">
      {items.map((row) => (
        <li key={row.signal.id} className="flex justify-between gap-3">
          <span>
            {row.series.series_name} #{row.issue.issue_number}
          </span>
          <span className="text-slate-400">{row.signal.signal_type}</span>
        </li>
      ))}
    </ul>
  );
}

export function ReleaseIntelligencePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ReleaseIntelligenceDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getReleaseIntelligenceDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load release intelligence dashboard.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Release Intelligence"
        title="Release Intelligence"
        description="Future-release tracking for publishers, FOC dates, release dates, new #1s, key issues, and variants (P50-01)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading release intelligence…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Upcoming Releases" value={String(dashboard.upcoming_releases.length)} />
            <StatCard label="FOC Entries" value={String(dashboard.foc_calendar.length)} />
            <StatCard label="New #1 Signals" value={String(dashboard.new_number_one_feed.length)} />
            <StatCard label="Key Signals" value={String(dashboard.key_issue_feed.length + dashboard.variant_feed.length)} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Variant Count" value={String(dashboard.variant_count)} />
            <StatCard label="Cover Variants" value={String(dashboard.cover_variant_count)} />
            <StatCard label="Ratio Variants" value={String(dashboard.ratio_variant_count)} />
            <StatCard label="Recent Variants" value={String(dashboard.recent_variants.length)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Upcoming Releases">
              <IssueList items={dashboard.upcoming_releases} />
            </Panel>

            <Panel title="FOC Calendar">
              <IssueList items={dashboard.foc_calendar} />
            </Panel>

            <Panel title="New #1 Feed">
              <SignalList items={dashboard.new_number_one_feed} />
            </Panel>

            <Panel title="Key Issue Feed">
              <SignalList items={dashboard.key_issue_feed} />
            </Panel>

            <Panel title="Variant Feed">
              <SignalList items={dashboard.variant_feed} />
            </Panel>

            <Panel title="Recent Variants">
              <VariantList items={dashboard.recent_variants} />
            </Panel>

            <Panel title="Recent Ratio Variants">
              <VariantList items={dashboard.top_ratio_variants} />
            </Panel>

            <Panel title="Agent Activity">
              {!dashboard.agent_activity.length ? (
                <p className="text-sm text-slate-500">No release intelligence runs yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.agent_activity.map((row) => (
                    <li key={row.id} className="flex justify-between gap-3">
                      <span>{row.agent_code}</span>
                      <span className="text-slate-400">{row.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
