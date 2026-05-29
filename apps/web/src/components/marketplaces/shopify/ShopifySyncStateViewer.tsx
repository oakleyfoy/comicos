import type { ShopifySyncStateResponse } from "../../../api/client";
import { ShopifyPublicationStatusBadge } from "./ShopifyPublicationStatusBadge";

export function ShopifySyncStateViewer({
  items,
}: {
  items: ShopifySyncStateResponse[];
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Sync state</p>
          <h2 className="mt-1 text-base font-semibold text-white">Storefront sync state viewer</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No sync states have been recorded yet.</p>
      ) : (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <article key={item.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-white">Storefront #{item.storefront_id}</p>
                  <p className="mt-1 text-xs text-slate-500">Sync state #{item.id}</p>
                </div>
                <ShopifyPublicationStatusBadge status={item.sync_status} />
              </div>
              <pre className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-xs text-slate-200">
                {JSON.stringify(item.sync_payload_json, null, 2)}
              </pre>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
