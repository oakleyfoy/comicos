import type { MarketplaceEventLineageResponse } from "../../../api/client";

export function MarketplaceEventLineageViewer({
  lineage,
}: {
  lineage: MarketplaceEventLineageResponse[];
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Lineage</p>
          <h2 className="mt-1 text-base font-semibold text-white">Append-only event history</h2>
        </div>
        <p className="text-sm text-slate-400">{lineage.length} entries</p>
      </div>
      {lineage.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No lineage entries for this event yet.</p>
      ) : (
        <div className="mt-4 space-y-3">
          {lineage.map((entry) => (
            <article key={entry.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                  {entry.lineage_event_type}
                </span>
                <span className="text-xs text-slate-500">{new Date(entry.created_at).toLocaleString()}</span>
              </div>
              <pre className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/70 p-3 text-xs text-slate-300">
                {JSON.stringify(entry.lineage_payload_json, null, 2)}
              </pre>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
