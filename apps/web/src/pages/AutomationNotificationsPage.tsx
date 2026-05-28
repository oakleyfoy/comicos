import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationAlertRead, type AutomationNotificationRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function shortenChecksum(value?: string | null): string {
  if (!value) return "—";
  if (value.length <= 18) return value;
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationNotificationsPage() {
  const [notifications, setNotifications] = useState<AutomationNotificationRead[]>([]);
  const [alerts, setAlerts] = useState<AutomationAlertRead[]>([]);
  const [selected, setSelected] = useState<AutomationNotificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh(selectedId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [notificationResponse, alertResponse] = await Promise.all([
        apiClient.listAutomationNotifications({ limit: 50, offset: 0 }),
        apiClient.listAutomationAlerts({ limit: 50, offset: 0 }),
      ]);
      setNotifications(notificationResponse.items);
      setAlerts(alertResponse.items);
      const nextId = selectedId ?? notificationResponse.items[0]?.id ?? null;
      if (nextId) {
        setSelected(await apiClient.getAutomationNotification(nextId));
      } else {
        setSelected(null);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load notification workspace.");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    const queued = notifications.filter((row) => row.notification_status === "QUEUED").length;
    const suppressed = notifications.filter((row) => row.notification_status === "SUPPRESSED").length;
    const failed = notifications.filter((row) => row.notification_status === "FAILED").length;
    const critical = alerts.filter((row) => row.alert_severity === "CRITICAL" && row.alert_status === "ACTIVE").length;
    return { queued, suppressed, failed, critical };
  }, [alerts, notifications]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-06"
        title="Notifications / Alerting / Operational Messaging"
        description="Deterministic replay-safe operational messaging for workflow failures, replay warnings, queue/runtime alerts, and maintenance notifications."
        actions={
          <Link to="/ops#automation-notification-ops" className="rounded-2xl border border-violet-400/35 px-4 py-2 text-sm font-semibold text-violet-100">
            Ops diagnostics
          </Link>
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Queued notifications" value={String(summary.queued)} />
        <StatCard label="Failed deliveries" value={String(summary.failed)} />
        <StatCard label="Active alerts" value={String(alerts.filter((row) => row.alert_status === "ACTIVE").length)} />
        <StatCard label="Critical alerts" value={String(summary.critical)} />
        <StatCard label="Suppressed" value={String(summary.suppressed)} />
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Notification ledger">
          {loading ? (
            <p className="text-sm text-slate-400">Loading notifications…</p>
          ) : notifications.length ? (
            <div className="space-y-3">
              {notifications.map((row) => (
                <button
                  key={row.id}
                  type="button"
                  onClick={() => void refresh(row.id)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-left transition hover:border-violet-300/40"
                >
                  <p className="text-sm font-semibold text-white">
                    {row.notification_type} · {row.notification_status}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{row.source_event_type} · checksum {shortenChecksum(row.notification_checksum)}</p>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="No notifications yet" description="Operational notifications appear here once automation events are routed into the messaging ledger." />
          )}
        </Panel>

        <Panel title="Alert panel">
          {alerts.length ? (
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div key={alert.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">{alert.alert_type}</p>
                  <p className="mt-1 text-xs text-slate-400">
                    {alert.alert_severity} · {alert.escalation_level} · {alert.alert_status}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No alerts recorded yet.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Delivery tracking">
          {selected?.deliveries.length ? (
            <div className="space-y-3">
              {selected.deliveries.map((delivery) => (
                <div key={delivery.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">
                    #{delivery.delivery_rank} · {delivery.delivery_channel}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{delivery.delivery_status} · {delivery.failure_reason ?? "—"}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Select a notification to inspect delivery lineage.</p>
          )}
        </Panel>

        <Panel title="History timeline">
          {selected?.history.length ? (
            <div className="space-y-3">
              {selected.history.map((entry) => (
                <div key={entry.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">{entry.event_type}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatDateTime(entry.created_at)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Append-only notification events appear here once a notification is selected.</p>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
