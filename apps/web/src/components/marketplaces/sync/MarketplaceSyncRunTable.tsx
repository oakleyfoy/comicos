import type { MarketplaceInventorySyncRunResponse } from "../../../api/client";

type Props = {
  runs: MarketplaceInventorySyncRunResponse[];
  loading: boolean;
};

export function MarketplaceSyncRunTable({ runs, loading }: Props): JSX.Element {
  if (loading) {
    return <p className="text-sm text-slate-400">Loading sync runs...</p>;
  }
  if (!runs.length) {
    return <p className="text-sm text-slate-500">No marketplace sync runs yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="bg-slate-900/80 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Run</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Processed</th>
            <th className="px-4 py-3">Conflicts</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((row) => (
            <tr key={row.id} className="border-t border-white/5">
              <td className="px-4 py-3">
                <p className="font-medium text-white">{row.sync_run_type}</p>
                <p className="text-xs text-slate-500">#{row.id}</p>
              </td>
              <td className="px-4 py-3 text-xs text-slate-300">{row.sync_status}</td>
              <td className="px-4 py-3 text-xs text-slate-300">{row.records_processed}</td>
              <td className="px-4 py-3 text-xs text-slate-300">{row.conflicts_detected}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
