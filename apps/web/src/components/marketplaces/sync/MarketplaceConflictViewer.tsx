import type { MarketplaceInventoryConflictResponse } from "../../../api/client";

type Props = {
  conflicts: MarketplaceInventoryConflictResponse[];
  loading: boolean;
};

export function MarketplaceConflictViewer({ conflicts, loading }: Props): JSX.Element {
  if (loading) {
    return <p className="text-sm text-slate-400">Loading marketplace conflicts...</p>;
  }
  if (!conflicts.length) {
    return <p className="text-sm text-slate-500">No marketplace sync conflicts detected.</p>;
  }
  return (
    <div className="space-y-3">
      {conflicts.map((row) => (
        <div key={row.id} className="rounded-2xl border border-rose-400/20 bg-rose-500/5 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-rose-100">{row.conflict_type}</p>
            <span className="rounded-full bg-rose-500/10 px-2 py-1 text-xs text-rose-200">{row.conflict_status}</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">State #{row.marketplace_inventory_state_id}</p>
          <pre className="mt-3 overflow-auto rounded-xl bg-black/30 p-3 text-xs text-amber-100">
            {JSON.stringify(
              {
                local: row.local_value_json,
                marketplace: row.marketplace_value_json,
              },
              null,
              2,
            )}
          </pre>
        </div>
      ))}
    </div>
  );
}
