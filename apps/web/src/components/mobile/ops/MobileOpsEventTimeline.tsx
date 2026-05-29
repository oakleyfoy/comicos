import type { MobileOpsEventResponse } from "../../../api/client";

export function MobileOpsEventTimeline({ events }: { events: MobileOpsEventResponse[] }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-lg font-semibold text-white">Ops Event Timeline</h2>
      <div className="mt-4 space-y-3">
        {events.length === 0 ? <p className="text-sm text-slate-400">No mobile ops events recorded yet.</p> : null}
        {events.map((event) => (
          <div key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">{event.event_type}</p>
              <p className="text-xs text-slate-500">#{event.id}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
