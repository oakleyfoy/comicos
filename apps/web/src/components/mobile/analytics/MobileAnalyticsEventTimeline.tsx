import type { MobileAnalyticsEventResponse } from "../../../api/client";

export function MobileAnalyticsEventTimeline({ events }: { events: MobileAnalyticsEventResponse[] }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <h2 className="text-lg font-semibold text-white">Analytics events</h2>
        <p className="mt-1 text-sm text-slate-400">Append-only analytics lineage for metric, trend, snapshot, and generation actions.</p>
      </div>
      <div className="mt-4 space-y-3">
        {events.map((event) => (
          <div key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">{event.event_type}</p>
              <p className="text-xs text-slate-500">{new Date(event.created_at).toLocaleString()}</p>
            </div>
            <p className="mt-2 text-xs text-slate-400">actor {event.actor_user_id ?? "n/a"}</p>
            <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950/80 p-3 text-xs text-slate-300">
              {JSON.stringify(event.event_payload_json, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </section>
  );
}
