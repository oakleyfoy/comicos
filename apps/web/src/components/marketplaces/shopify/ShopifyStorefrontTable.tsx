import type { ShopifyStorefrontResponse } from "../../../api/client";
import { ShopifyPublicationStatusBadge } from "./ShopifyPublicationStatusBadge";

export function ShopifyStorefrontTable({
  items,
  selectedStorefrontId,
  canManage,
  busyStorefrontId,
  onSelect,
  onSnapshot,
}: {
  items: ShopifyStorefrontResponse[];
  selectedStorefrontId: number | null;
  canManage: boolean;
  busyStorefrontId: number | null;
  onSelect: (storefrontId: number) => void;
  onSnapshot: (storefrontId: number) => Promise<void>;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Storefronts</p>
          <h2 className="mt-1 text-base font-semibold text-white">Shopify storefront registry</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No storefronts have been registered yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Storefront</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Identifier</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer bg-slate-950/35 text-slate-200 ${selectedStorefrontId === item.id ? "ring-1 ring-violet-400/30" : ""}`}
                  onClick={() => onSelect(item.id)}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{item.storefront_name}</p>
                    <p className="mt-1 text-xs text-slate-500">Marketplace account #{item.marketplace_account_id}</p>
                  </td>
                  <td className="px-4 py-3">
                    <ShopifyPublicationStatusBadge status={item.storefront_status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">{item.storefront_identifier}</td>
                  <td className="px-4 py-3">
                    {canManage ? (
                      <button
                        type="button"
                        disabled={busyStorefrontId === item.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          void onSnapshot(item.id);
                        }}
                        className="rounded-2xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {busyStorefrontId === item.id ? "Snapshotting..." : "Generate snapshot"}
                      </button>
                    ) : (
                      <p className="text-xs text-slate-500">View only</p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
