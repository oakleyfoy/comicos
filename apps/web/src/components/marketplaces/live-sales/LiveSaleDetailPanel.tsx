import type { LiveSaleDetailResponse } from "../../../api/client";

export function LiveSaleDetailPanel({
  detail,
  canManage,
  busySessionAction,
  onStart,
  onEnd,
}: {
  detail: LiveSaleDetailResponse | null;
  canManage: boolean;
  busySessionAction: boolean;
  onStart: (sessionId: number) => Promise<void>;
  onEnd: (sessionId: number) => Promise<void>;
}): JSX.Element {
  if (!detail) {
    return (
      <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-400">
        Select a session to see the detail panel, events, queue state, and claim context.
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Session detail</p>
          <h2 className="mt-1 text-base font-semibold text-white">{detail.session.session_name}</h2>
          <p className="mt-1 text-sm text-slate-400">Session #{detail.session.id}</p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
          {detail.session.session_status}
        </span>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Metric label="Queue items" value={String(detail.queue_items.length)} />
        <Metric label="Claims" value={String(detail.claims.length)} />
        <Metric label="Events" value={String(detail.events.length)} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!canManage || busySessionAction}
          onClick={() => void onStart(detail.session.id)}
          className="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Start
        </button>
        <button
          type="button"
          disabled={!canManage || busySessionAction}
          onClick={() => void onEnd(detail.session.id)}
          className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          End
        </button>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Operational timings</p>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            <p>Planned start: {detail.session.planned_start_at ? new Date(detail.session.planned_start_at).toLocaleString() : "n/a"}</p>
            <p>Planned end: {detail.session.planned_end_at ? new Date(detail.session.planned_end_at).toLocaleString() : "n/a"}</p>
            <p>Started: {detail.session.started_at ? new Date(detail.session.started_at).toLocaleString() : "n/a"}</p>
            <p>Ended: {detail.session.ended_at ? new Date(detail.session.ended_at).toLocaleString() : "n/a"}</p>
          </div>
        </section>
        <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Session events</p>
          <div className="mt-3 space-y-2 text-xs text-slate-300">
            {detail.events.length === 0 ? <p>No session events yet.</p> : null}
            {detail.events.map((event) => (
              <article key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/70 p-3">
                <p className="font-semibold text-white">{event.event_type}</p>
                <p className="mt-1 text-slate-500">{new Date(event.created_at).toLocaleString()}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}
