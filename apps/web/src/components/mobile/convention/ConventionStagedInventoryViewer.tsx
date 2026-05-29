export function ConventionStagedInventoryViewer({
  items,
}: {
  items: import("../../../api/client").ConventionInventoryStageResponse[];
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No staged convention inventory.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="border-b border-white/10 bg-slate-950/60 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Item</th>
            <th className="px-4 py-3">Session</th>
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id} className="border-b border-white/5">
              <td className="px-4 py-3">#{row.inventory_item_id}</td>
              <td className="px-4 py-3">#{row.convention_session_id}</td>
              <td className="px-4 py-3">{row.stage_status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
