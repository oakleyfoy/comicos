import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type KeyIssueDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getKeyIssuesDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load key issue intelligence.");
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
        eyebrow="Key issues"
        title="Key Issue Intelligence"
        description="Why an issue matters — first appearances, origins, milestones, anniversaries, and universe launches (P51-02)."
      />

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
