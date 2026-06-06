import { useEffect, useState } from "react";

import { ApiError, apiClient, type P79StorageAnalyticsDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function StorageAnalyticsPage(): JSX.Element {
  const [dash, setDash] = useState<P79StorageAnalyticsDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const body = await apiClient.getStorageAnalyticsDashboard();
        if (!cancelled) setDash(body);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to load analytics.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const a = dash?.analytics;
  const h = dash?.health;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Storage"
        title="Storage Analytics"
        description="Health, capacity, utilization, audits, and unassigned inventory (P79-03)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {dash && a && h ? (
        <div className="space-y-8">
          <section className="grid gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">Storage health</p>
              <p className="text-2xl font-semibold">
                {h.health_score} / 100 — {h.health_status}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">Utilization</p>
              <p className="text-2xl font-semibold">{a.utilization_pct}%</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">Forecast</p>
              <p className="text-2xl font-semibold">{a.forecast_risk}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">Unassigned</p>
              <p className="text-2xl font-semibold">{dash.unassigned.total_unassigned}</p>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold">Capacity overview</h2>
            <p className="text-sm text-slate-700">
              {a.used_capacity} / {a.total_capacity} slots used — {a.available_capacity} available —{" "}
              {a.over_capacity_boxes} over-capacity boxes
            </p>
          </section>

          <section>
            <h2 className="text-sm font-semibold">Utilization by location</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dash.utilization.slice(0, 12).map((u, i) => (
                <li key={`${u.group_kind}-${u.group_key}-${i}`}>
                  {u.group_kind} {u.group_key}: {u.utilization_pct}%
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold">Audit performance</h2>
            <p className="text-sm text-slate-700">
              Started {dash.audit_analytics.audits_started}, completed {dash.audit_analytics.audits_completed},
              accuracy {dash.audit_analytics.audit_accuracy_rate_pct}%
            </p>
          </section>

          <section>
            <h2 className="text-sm font-semibold">High-value unassigned</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dash.unassigned.items
                .filter((i) => i.high_value)
                .slice(0, 8)
                .map((i) => (
                  <li key={i.inventory_copy_id}>
                    {i.title} (copy {i.inventory_copy_id})
                  </li>
                ))}
            </ul>
          </section>

          {dash.over_capacity_alerts.length > 0 ? (
            <section>
              <h2 className="text-sm font-semibold text-amber-800">Over-capacity alerts</h2>
              <ul className="mt-2 text-sm text-amber-900">
                {dash.over_capacity_alerts.map((b) => (
                  <li key={b.entity_id ?? b.group_key}>
                    Box {b.group_key}: {b.utilization_pct}%
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
