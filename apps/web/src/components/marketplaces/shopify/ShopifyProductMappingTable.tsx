import type { ShopifyProductMappingResponse } from "../../../api/client";
import { ShopifyPublicationStatusBadge } from "./ShopifyPublicationStatusBadge";

export function ShopifyProductMappingTable({
  items,
  selectedMappingId,
  onSelect,
}: {
  items: ShopifyProductMappingResponse[];
  selectedMappingId: number | null;
  onSelect: (mappingId: number) => void;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Mappings</p>
          <h2 className="mt-1 text-base font-semibold text-white">Product mapping registry</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No product mappings have been created yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Identifier</th>
                <th className="px-4 py-3">Mapping</th>
                <th className="px-4 py-3">Inventory / Draft</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer bg-slate-950/35 text-slate-200 ${selectedMappingId === item.id ? "ring-1 ring-violet-400/30" : ""}`}
                  onClick={() => onSelect(item.id)}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{item.storefront_product_identifier}</p>
                    <p className="mt-1 text-xs text-slate-500">Mapping #{item.id}</p>
                  </td>
                  <td className="px-4 py-3">
                    <ShopifyPublicationStatusBadge status={item.mapping_status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    <p>Inventory #{item.inventory_item_id}</p>
                    <p>Draft #{item.marketplace_listing_draft_id}</p>
                    <p>Updated {item.updated_at}</p>
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
