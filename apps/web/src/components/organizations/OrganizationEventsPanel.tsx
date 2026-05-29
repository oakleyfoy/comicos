import { EmptyState } from "../EmptyState";
import type { OrganizationEventResponse } from "../../api/client";

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function OrganizationEventsPanel({ events }: { events: OrganizationEventResponse[] }): JSX.Element {
  if (!events.length) {
    return <EmptyState title="No events yet" description="Append-only organization lifecycle events will appear here as members are invited, accepted, archived, or removed." />;
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Audit lineage</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Organization events</h2>
      </div>
      <div className="mt-4 space-y-3">
        {events.map((event) => (
          <div key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium text-white">{event.event_type}</p>
                <p className="mt-1 text-sm text-slate-400">Actor {event.actor_user_id ?? "system"}</p>
              </div>
              <p className="text-xs text-slate-400">{formatDateTime(event.created_at)}</p>
            </div>
            <pre className="mt-3 overflow-x-auto rounded-2xl bg-slate-950/70 p-3 text-xs text-slate-300">
              {JSON.stringify(event.event_payload_json, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </section>
  );
}
