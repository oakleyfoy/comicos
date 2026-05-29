import type { UserAuthSessionRead } from "../../api/client";

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function AuthSessionListPanel({
  sessions,
  revoking,
  onRevoke,
  onRevokeAll,
}: {
  sessions: UserAuthSessionRead[];
  revoking: string | null;
  onRevoke: (sessionId: number) => Promise<void>;
  onRevokeAll: () => Promise<void>;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Auth sessions</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Device and session activity</h2>
        </div>
        <button
          type="button"
          onClick={() => void onRevokeAll()}
          disabled={revoking === "all"}
          className="rounded-2xl border border-rose-400/35 px-4 py-2 text-sm font-semibold text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {revoking === "all" ? "Revoking..." : "Revoke all"}
        </button>
      </div>
      <div className="mt-4 space-y-3">
        {sessions.map((authSession) => (
          <div key={authSession.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium text-white">
                  {authSession.device_label} {authSession.is_current ? "• Current" : ""}
                </p>
                <p className="mt-1 text-sm text-slate-400">
                  {authSession.device_type} • issued {formatDateTime(authSession.issued_at)} • last seen {formatDateTime(authSession.last_seen_at)}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Status {authSession.session_status} • expires {formatDateTime(authSession.expires_at)}
                </p>
              </div>
              <button
                type="button"
                disabled={authSession.session_status !== "ACTIVE" || revoking === String(authSession.id)}
                onClick={() => void onRevoke(authSession.id)}
                className="rounded-2xl border border-rose-400/35 px-4 py-2 text-sm font-semibold text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {revoking === String(authSession.id) ? "Revoking..." : "Revoke"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
