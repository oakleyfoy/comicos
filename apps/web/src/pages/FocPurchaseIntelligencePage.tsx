import { useEffect, useState } from "react";

import { ApiError, apiClient, type P74FocDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function FocPurchaseIntelligencePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<P74FocDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getFocPurchaseDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load FOC purchase intelligence.");
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

  const w = dashboard?.foc_watch;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Release intelligence"
        title="FOC & Purchase Intelligence"
        description="Preorder priorities and quantity guidance (P74-02). Advisory only — no auto-ordering."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {dashboard && w ? (
        <div className="space-y-8">
          <section className="grid gap-3 sm:grid-cols-5">
            {[
              ["This week", w.foc_this_week],
              ["Next week", w.foc_next_week],
              ["30 days", w.foc_within_30_days],
              ["Missed", w.foc_missed],
              ["Unknown", w.foc_unknown],
            ].map(([label, n]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-slate-500">FOC {label}</p>
                <p className="text-2xl font-semibold text-slate-900">{n}</p>
              </div>
            ))}
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Recommended preorders</h2>
            <ul className="mt-2 space-y-2 text-sm text-slate-700">
              {dashboard.recommended_preorders.slice(0, 12).map((r) => (
                <li key={r.id}>
                  {r.publisher} {r.series_name} #{r.issue_number} — {r.purchase_action} ×{r.quantity_recommended}{" "}
                  <span className="text-slate-500">(priority {r.priority_score})</span>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Quantity / recommendation changes</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dashboard.quantity_changes.slice(0, 10).map((c) => (
                <li key={c.id}>
                  Issue {c.release_issue_id}: {c.previous_action} {c.previous_quantity} → {c.current_action}{" "}
                  {c.current_quantity} ({c.change_kind})
                </li>
              ))}
            </ul>
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Upgrades</h2>
              <ul className="mt-2 text-sm text-slate-700">
                {dashboard.recommendation_upgrades.slice(0, 8).map((c) => (
                  <li key={c.id}>
                    {c.previous_action} → {c.current_action}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Missed FOC</h2>
              <ul className="mt-2 text-sm text-slate-700">
                {dashboard.missed_foc.slice(0, 8).map((r) => (
                  <li key={r.id}>
                    {r.series_name} #{r.issue_number}
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Watchlist matches</h2>
            <ul className="mt-2 text-sm text-slate-700">
              {dashboard.watchlist_matches.slice(0, 8).map((r) => (
                <li key={r.id}>
                  {r.series_name} #{r.issue_number} — {r.purchase_action}
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
