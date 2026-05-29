import type { MarketplaceEventResponse } from "../../../api/client";
import { MarketplaceEventStatusBadge } from "./MarketplaceEventStatusBadge";

export function MarketplaceEventTable({
  items,
  selectedEventId,
  onSelect,
}: {
  items: MarketplaceEventResponse[];
  selectedEventId: number | null;
  onSelect: (eventId: number) => void;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Events</p>
          <h2 className="mt-1 text-base font-semibold text-white">Marketplace event inbox</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No marketplace events have been ingested yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Event</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Received</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer bg-slate-950/35 text-slate-200 ${selectedEventId === item.id ? "ring-1 ring-violet-400/30" : ""}`}
                  onClick={() => onSelect(item.id)}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">#{item.id}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.external_event_identifier}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">{item.event_type}</td>
                  <td className="px-4 py-3">
                    <MarketplaceEventStatusBadge status={item.event_status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">{new Date(item.received_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
