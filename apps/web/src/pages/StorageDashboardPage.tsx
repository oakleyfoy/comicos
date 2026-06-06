import { useEffect, useState } from "react";

import { ApiError, apiClient, type P79StorageDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function StorageDashboardPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<P79StorageDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const body = await apiClient.getStorageDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to load dashboard.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const d = dashboard;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Storage"
        title="Storage Dashboard"
        description="Locations, boxes, assignments, and capacity (P79-01)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {d ? (
        <div className="space-y-8">
          <section className="grid gap-3 sm:grid-cols-4">
            {[
              ["Locations", d.location_count],
              ["Boxes", d.box_count],
              ["Assigned", d.assigned_books],
              ["Unassigned", d.unassigned_books],
            ].map(([label, n]) => (
              <div key={String(label)} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="text-2xl font-semibold text-slate-900">{n}</p>
              </div>
            ))}
          </section>
          <section className="grid gap-3 sm:grid-cols-3">
            {[
              ["Box utilization", `${d.box_utilization_pct}%`],
              ["Shelf utilization", `${d.shelf_utilization_pct}%`],
              ["Available slots", d.available_slots],
            ].map(([label, n]) => (
              <div key={String(label)} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="text-xl font-semibold text-slate-900">{n}</p>
              </div>
            ))}
          </section>
          <section>
            <h2 className="text-sm font-semibold text-slate-900">Recent assignments</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {d.recent_assignments.map((a) => (
                <li key={a.id}>
                  Copy {a.inventory_copy_id}: {a.series_name} #{a.issue_number} — {a.box_name} slot {a.slot_number}
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
