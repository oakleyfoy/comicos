import { useEffect, useState } from "react";

import { ApiError, apiClient, type P74ReleaseMonitoringDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ReleaseMonitoringPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<P74ReleaseMonitoringDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getReleaseMonitoringDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load release monitoring.");
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

  const up = dashboard?.upcoming;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Release intelligence"
        title="Release Monitoring"
        description="Upcoming releases, catalog changes, and watchlist activity (P74-01)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {dashboard && up ? (
        <div className="space-y-8">
          <section>
            <h2 className="text-sm font-semibold text-slate-900">Upcoming releases</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-4">
              {[
                ["This week", up.this_week.length],
                ["Next week", up.next_week.length],
                ["30 days", up.next_30_days.length],
                ["90 days", up.next_90_days.length],
              ].map(([label, n]) => (
                <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs text-slate-500">{label}</p>
                  <p className="text-2xl font-semibold text-slate-900">{n}</p>
                </div>
              ))}
            </div>
            <ul className="mt-4 space-y-2 text-sm text-slate-700">
              {up.next_30_days.slice(0, 8).map((r) => (
                <li key={r.issue_id}>
                  {r.publisher} — {r.series_name} #{r.issue_number} ({r.release_date ?? "TBD"}) ·{" "}
                  {r.variant_count} variants
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Recent changes</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dashboard.recent_changes.slice(0, 10).map((c) => (
                <li key={c.id}>
                  {c.change_type} · issue {c.issue_id ?? "—"} · {new Date(c.detected_at).toLocaleString()}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">New #1 issues</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dashboard.new_number_ones
                .filter((h) => h.category === "NEW_NUMBER_ONE" || h.category === "NEW_SERIES")
                .slice(0, 8)
                .map((h) => (
                  <li key={`${h.category}-${h.issue_id}`}>
                    {h.publisher} {h.series_name} #{h.issue_number}
                  </li>
                ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Variant changes</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dashboard.variant_changes.slice(0, 8).map((v) => (
                <li key={v.change_id}>
                  {v.variant_name}
                  {v.late_added ? " (late-added)" : ""}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Watchlist activity</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dashboard.watchlist_activity.map((w) => (
                <li key={w.watchlist_id}>
                  {w.watchlist_name}: {w.changes_since_review} changes (14d)
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
