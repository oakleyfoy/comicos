import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type ContinuityDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

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

export function ReleaseWatchlistPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ContinuityDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getReleaseWatchlistDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load release watchlists dashboard.");
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
        eyebrow="Release Watchlists"
        title="Release Watchlists"
        description="Continuity alerts, FOC reminders, release reminders, and watchlist tracking for upcoming comics (P50-02)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading release watchlists…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Active Runs" value={String(dashboard.active_runs.length)} />
            <StatCard label="Alerts" value={String(dashboard.continuity_alerts.length)} />
            <StatCard label="FOC Reminders" value={String(dashboard.foc_reminders.length)} />
            <StatCard label="Watchlists" value={String(dashboard.watchlists.length)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Active Runs">
              {!dashboard.active_runs.length ? (
                <p className="text-sm text-slate-500">No tracked runs yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.active_runs.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>
                        {row.series_name} ({row.publisher})
                      </span>
                      <span className="text-slate-400">#{row.latest_issue_owned}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Continue Run Alerts">
              {!dashboard.continuity_alerts.filter((row) => row.alert_type === "CONTINUE_RUN").length ? (
                <p className="text-sm text-slate-500">No continue-run alerts.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.continuity_alerts
                    .filter((row) => row.alert_type === "CONTINUE_RUN")
                    .map((row) => (
                      <li key={row.id}>{row.alert_type}</li>
                    ))}
                </ul>
              )}
            </Panel>

            <Panel title="Missing Issue Risks">
              {!dashboard.continuity_alerts.filter((row) => row.alert_type === "MISSING_ISSUE_RISK").length ? (
                <p className="text-sm text-slate-500">No missing issue risks.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.continuity_alerts
                    .filter((row) => row.alert_type === "MISSING_ISSUE_RISK")
                    .map((row) => (
                      <li key={row.id}>{row.alert_type}</li>
                    ))}
                </ul>
              )}
            </Panel>

            <Panel title="FOC Reminders">
              {!dashboard.foc_reminders.length ? (
                <p className="text-sm text-slate-500">No FOC reminders.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.foc_reminders.map((row) => (
                    <li key={row.id}>{row.reminder_type}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Release Reminders">
              {!dashboard.release_reminders.length ? (
                <p className="text-sm text-slate-500">No release reminders.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.release_reminders.map((row) => (
                    <li key={row.id}>{row.reminder_type}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Watchlists">
              {!dashboard.watchlists.length ? (
                <p className="text-sm text-slate-500">No watchlists yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.watchlists.map((row) => (
                    <li key={row.watchlist.id} className="flex justify-between gap-2">
                      <span>{row.watchlist.watchlist_name}</span>
                      <span className="text-slate-400">{row.items.length} items</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Watched Upcoming Releases">
              {!dashboard.upcoming_watched_releases.length ? (
                <p className="text-sm text-slate-500">No watched upcoming releases.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.upcoming_watched_releases.map((row) => (
                    <li key={row.id}>
                      {row.title} #{row.issue_number}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Agent Activity">
              {!dashboard.agent_activity.length ? (
                <p className="text-sm text-slate-500">No watchlist agent runs yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.agent_activity.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
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
