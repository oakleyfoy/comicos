import type { OrganizationNotificationResponse } from "../../../api/client";

type Props = {
  notifications: OrganizationNotificationResponse[];
  unreadCount: number;
  busy: boolean;
  onMarkRead: (notificationId: number) => void;
  onAcknowledge: (notificationId: number) => void;
};

export function OrganizationNotificationCenter({
  notifications,
  unreadCount,
  busy,
  onMarkRead,
  onAcknowledge,
}: Props): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-white">Notification center</h2>
        {unreadCount > 0 ? (
          <span className="rounded-full bg-rose-500/20 px-3 py-1 text-xs font-semibold text-rose-100">
            {unreadCount} unread
          </span>
        ) : (
          <span className="text-xs text-slate-500">All caught up</span>
        )}
      </div>
      {!notifications.length ? (
        <p className="text-sm text-slate-500">No notifications for your account in this organization.</p>
      ) : (
        <ul className="space-y-3">
          {notifications.map((row) => (
            <li key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-white">{row.notification_title}</p>
                  <p className="mt-1 text-sm text-slate-300">{row.notification_body}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    {row.notification_type} · {row.notification_status}
                  </p>
                </div>
                <div className="flex flex-col gap-2">
                  {row.notification_status === "UNREAD" ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onMarkRead(row.id)}
                      className="rounded-xl border border-cyan-400/30 px-3 py-1 text-xs font-semibold text-cyan-100 disabled:opacity-50"
                    >
                      Mark read
                    </button>
                  ) : null}
                  {row.notification_status !== "ACKNOWLEDGED" ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onAcknowledge(row.id)}
                      className="rounded-xl border border-violet-400/30 px-3 py-1 text-xs font-semibold text-violet-100 disabled:opacity-50"
                    >
                      Acknowledge
                    </button>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
