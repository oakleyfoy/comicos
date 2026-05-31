import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type ReleaseOpportunityDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { VariantList } from "../components/VariantList";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function ReleasePlatformPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ReleaseOpportunityDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getReleasePlatformDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load release platform dashboard.");
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

  const budget = dashboard?.budget_forecast;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Release planning"
        title="Release Platform"
        description="Forward-looking horizons, opportunities, buy queue, run planning, and budget forecast — advisory only (P50-04)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading release platform…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="New Announcements" value={String(dashboard.new_announcements.length)} />
            <StatCard label="Next 30 Days" value={String(dashboard.next_30_days.length)} />
            <StatCard label="Next 60 Days" value={String(dashboard.next_60_days.length)} />
            <StatCard label="Next 90 Days" value={String(dashboard.next_90_days.length)} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Variant Count" value={String(dashboard.variant_count)} />
            <StatCard label="Cover Variants" value={String(dashboard.cover_variant_count)} />
            <StatCard label="Ratio Variants" value={String(dashboard.ratio_variant_count)} />
            <StatCard label="New Variants" value={String(dashboard.top_new_variants.length)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="New Announcements">
              {!dashboard.new_announcements.length ? (
                <p className="text-sm text-slate-500">No long-range announcements.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.new_announcements.map((row) => (
                    <li key={row.issue.id}>
                      {row.series.series_name} #{row.issue.issue_number}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Next 30 Days">
              {!dashboard.next_30_days.length ? (
                <p className="text-sm text-slate-500">Nothing in the next 30 days.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.next_30_days.map((row) => (
                    <li key={row.issue.id}>{row.issue.title}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Next 60 Days">
              {!dashboard.next_60_days.length ? (
                <p className="text-sm text-slate-500">Nothing in the next 60 days.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.next_60_days.map((row) => (
                    <li key={row.issue.id}>{row.issue.title}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Next 90 Days">
              {!dashboard.next_90_days.length ? (
                <p className="text-sm text-slate-500">Nothing in the next 90 days.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.next_90_days.map((row) => (
                    <li key={row.issue.id}>{row.issue.title}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Top New #1s">
              {!dashboard.top_new_number_ones.length ? (
                <p className="text-sm text-slate-500">No #1 opportunities ranked.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.top_new_number_ones.map((row) => (
                    <li key={row.release_issue_id} className="flex justify-between gap-2">
                      <span>{row.issue.title}</span>
                      <span>{row.ranking_score.toFixed(1)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Top First Appearances">
              {!dashboard.top_first_appearances.length ? (
                <p className="text-sm text-slate-500">No first-appearance opportunities.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.top_first_appearances.map((row) => (
                    <li key={row.release_issue_id}>{row.issue.title}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Top Milestone Issues">
              {!dashboard.top_milestone_issues.length ? (
                <p className="text-sm text-slate-500">No milestone opportunities.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.top_milestone_issues.map((row) => (
                    <li key={row.release_issue_id}>{row.issue.title}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Top Variant Opportunities">
              {!dashboard.top_variants.length ? (
                <p className="text-sm text-slate-500">No variant opportunities.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.top_variants.map((row) => (
                    <li key={row.release_issue_id}>{row.issue.title}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Recent Ratio Variants">
              <VariantList items={dashboard.top_ratio_variants} />
            </Panel>

            <Panel title="Recent Variants">
              <VariantList items={dashboard.top_new_variants} />
            </Panel>

            <Panel title="Top Spec Opportunities">
              {!dashboard.top_spec_opportunities.length ? (
                <p className="text-sm text-slate-500">Run spec scoring to populate opportunities.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.top_spec_opportunities.map((row) => (
                    <li key={row.release_issue_id} className="flex justify-between gap-2">
                      <span>{row.issue.title}</span>
                      <span>{row.ranking_score.toFixed(1)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Continue Run Alerts">
              {!dashboard.continue_run_alerts.length ? (
                <p className="text-sm text-slate-500">No continue-run plans.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.continue_run_alerts.map((row) => (
                    <li key={row.release_issue_id}>
                      {row.series_name} #{row.target_issue_number} — {row.plan_type}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Start Following">
              {!dashboard.start_following_alerts.length ? (
                <p className="text-sm text-slate-500">No start-following alerts.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.start_following_alerts.map((row) => (
                    <li key={row.release_issue_id}>
                      {row.series_name} #{row.target_issue_number}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="New Opportunities">
              {!dashboard.new_opportunity_alerts.length ? (
                <p className="text-sm text-slate-500">No new-series opportunities flagged.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.new_opportunity_alerts.map((row) => (
                    <li key={row.release_issue_id}>
                      {row.series_name} #{row.target_issue_number}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Future Buy Queue (90 Days)">
              {!dashboard.future_buy_queue.next_90_days.length ? (
                <p className="text-sm text-slate-500">No queued buys for the next 90 days.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.future_buy_queue.next_90_days.slice(0, 8).map((row) => (
                    <li key={row.release_issue_id} className="flex justify-between gap-2">
                      <span>{row.buy_category}</span>
                      <span>{row.ranking_score.toFixed(1)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Budget Forecast">
              {!budget ? (
                <p className="text-sm text-slate-500">No budget forecast.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  <li>30 days: ${budget.expected_spend_total_30.toFixed(2)}</li>
                  <li>60 days: ${budget.expected_spend_total_60.toFixed(2)}</li>
                  <li>90 days: ${budget.expected_spend_total_90.toFixed(2)}</li>
                </ul>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
