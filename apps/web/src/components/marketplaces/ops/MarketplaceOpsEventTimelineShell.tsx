import type { MarketplaceOpsEventResponse } from "../../../api/client";
import { MarketplaceOpsStatusBadge } from "./MarketplaceOpsStatusBadge";

export function MarketplaceOpsEventTimelineShell({
  events,
}: {
  events: MarketplaceOpsEventResponse[];
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Event timeline</p>
          <h2 className="mt-1 text-base font-semibold text-white">Marketplace ops event timeline</h2>
        </div>
        <p className="text-sm text-slate-400">{events.length} visible</p>
      </div>
      {events.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No ops events have been recorded yet.</p>
      ) : (
        <div className="mt-4 space-y-3">
          {events.map((event) => (
            <article key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-white">{event.event_type}</p>
                  <p className="mt-1 text-xs text-slate-500">{event.created_at}</p>
                </div>
                <MarketplaceOpsStatusBadge status="accessed" />
              </div>
              <pre className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-xs text-slate-200">
                {JSON.stringify(event.event_payload_json, null, 2)}
              </pre>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
