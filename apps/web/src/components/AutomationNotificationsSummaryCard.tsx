import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationNotificationRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationNotificationsSummaryCard() {
  const [latest, setLatest] = useState<AutomationNotificationRead | null>(null);
  const [stats, setStats] = useState({ queued: 0, failed: 0, active: 0, critical: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const runs = await apiClient.listAutomationNotifications({ limit: 12, offset: 0 });
        if (ignore) return;
        setLatest(runs.items[0] ?? null);
        setStats({
          queued: runs.queued_count,
          failed: runs.failed_delivery_count,
          active: runs.active_alert_count,
          critical: runs.critical_alert_count,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load notification summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latest) return null;

  return (
    <section className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-violet-200/70">Automation notifications</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Notification and alert summary</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-notifications" className="rounded-full border border-violet-400/35 px-3 py-1.5 text-xs font-semibold text-violet-100">
            Open notification workspace
          </Link>
          <Link to="/ops#automation-notification-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading notification summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latest ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest notification" value={`#${latest.id}`} />
          <StatCard label="Queued" value={String(stats.queued)} />
          <StatCard label="Failed deliveries" value={String(stats.failed)} />
          <StatCard label="Active / critical alerts" value={`${stats.active} / ${stats.critical}`} />
        </div>
      ) : null}
    </section>
  );
}
