import type { MarketplaceInventoryStateResponse } from "../../../api/client";

type Props = {
  states: MarketplaceInventoryStateResponse[];
  loading: boolean;
};

export function MarketplaceInventoryStateTable({ states, loading }: Props): JSX.Element {
  if (loading) {
    return <p className="text-sm text-slate-400">Loading inventory state registry...</p>;
  }
  if (!states.length) {
    return <p className="text-sm text-slate-500">No marketplace inventory states registered yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="bg-slate-900/80 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Identifier</th>
            <th className="px-4 py-3">Inventory</th>
            <th className="px-4 py-3">Local</th>
            <th className="px-4 py-3">Marketplace</th>
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {states.map((row) => (
            <tr key={row.id} className="border-t border-white/5">
              <td className="px-4 py-3 font-mono text-xs text-slate-300">{row.marketplace_listing_identifier}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-400">#{row.inventory_item_id}</td>
              <td className="px-4 py-3 text-xs text-slate-300">{row.local_quantity}</td>
              <td className="px-4 py-3 text-xs text-slate-300">{row.marketplace_quantity}</td>
              <td className="px-4 py-3 text-xs text-slate-300">{row.sync_status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
