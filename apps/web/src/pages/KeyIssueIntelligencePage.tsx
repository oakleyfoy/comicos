import { useCallback, useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type KeyIssueDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function IssueList({ items }: { items: KeyIssueDashboardRead["top_key_issues"] }): JSX.Element {
  if (!items.length) {
    return <p className="text-sm text-slate-500">No key issues in this bucket yet.</p>;
  }
  return (
    <ul className="space-y-2 text-sm text-blue-900">
      {items.map((row) => (
        <li key={row.id} className="flex justify-between gap-2">
          <span>
            {row.series_name} #{row.issue_number} · {row.classification}
          </span>
          <span className="text-blue-700">{row.scores.overall_key_issue_score.toFixed(1)}</span>
        </li>
      ))}
    </ul>
  );
}

export function KeyIssueIntelligencePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<KeyIssueDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadStatus, setLoadStatus] = useState<string | undefined>();
  const [loadMessage, setLoadMessage] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.getKeyIssuesDashboard();
      setDashboard(body);
      setLoadStatus(body.status);
      setLoadMessage(body.message);
    } catch (err) {
      setDashboard(null);
      setLoadStatus(undefined);
      setLoadMessage(undefined);
      setError(err instanceof ApiError ? err.message : "Unable to load key issue intelligence.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function runRefresh() {
    setRefreshing(true);
    setError(null);
    try {
      await apiClient.postKeyIssuesRefresh();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh key issue intelligence.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Key issues"
        title="Key Issue Intelligence"
        description="Why an issue matters — first appearances, origins, milestones, anniversaries, and universe launches (P51-02)."
        actions={
          <button
            type="button"
            className="rounded-lg bg-patriot-blue px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            disabled={loading || refreshing}
            onClick={() => void runRefresh()}
          >
            {refreshing ? "Refreshing…" : "Refresh detection"}
          </button>
        }
      />

      <NavPageLoadBanner status={loadStatus} message={loadMessage} />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading key issue intelligence…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <p className="text-sm text-slate-600">{dashboard.total_profiles} key issue profiles indexed for your catalog.</p>
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Top Key Issues">
              <IssueList items={dashboard.top_key_issues} />
            </Panel>
            <Panel title="Highest Importance Scores">
              <IssueList items={dashboard.highest_importance} />
            </Panel>
            <Panel title="First Appearances">
              <IssueList items={dashboard.first_appearances} />
            </Panel>
            <Panel title="Origins">
              <IssueList items={dashboard.origins} />
            </Panel>
            <Panel title="Milestones">
              <IssueList items={dashboard.milestones} />
            </Panel>
            <Panel title="Anniversaries">
              <IssueList items={dashboard.anniversaries} />
            </Panel>
            <Panel title="Universe Launches">
              <IssueList items={dashboard.universe_launches} />
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
