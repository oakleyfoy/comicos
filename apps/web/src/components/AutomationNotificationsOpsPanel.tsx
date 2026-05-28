import { useEffect, useState } from "react";

import { ApiError, apiClient } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationNotificationsOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({ critical: 0, failures: 0, issues: 0, notifications: 0 });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [notifications, critical, issues] = await Promise.all([
          apiClient.listOpsAutomationNotifications({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationCriticalAlerts({ limit: 100, offset: 0 }),
          apiClient.listAutomationNotificationIssues({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          notifications: notifications.pagination.total_count,
          critical: critical.pagination.total_count,
          failures: notifications.failed_delivery_count,
          issues: issues.pagination.total_count,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load notification ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-notification-ops" className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation notification ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Critical alerts, failed deliveries, escalation diagnostics, routing conflicts, checksum diagnostics, and suppressed notification review.
          </p>
        </div>
        <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
          Ops / P41-06
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading notification ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Notifications" value={String(stats.notifications)} />
          <StatCard label="Critical alerts" value={String(stats.critical)} />
          <StatCard label="Failed deliveries" value={String(stats.failures)} />
          <StatCard label="Notification issues" value={String(stats.issues)} />
        </div>
      )}
    </section>
  );
}
