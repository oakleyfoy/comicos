function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function OfflineInventoryTable({
  items,
}: {
  items: import("../../../api/client").OfflineInventoryRecordResponse[];
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No offline inventory records.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="border-b border-white/10 bg-slate-950/60 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Local id</th>
            <th className="px-4 py-3">Item</th>
            <th className="px-4 py-3">Updated</th>
            <th className="px-4 py-3">Payload</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id} className="border-b border-white/5 last:border-0">
              <td className="px-4 py-3 font-mono text-xs">{row.local_record_identifier}</td>
              <td className="px-4 py-3">{row.inventory_item_id ?? "—"}</td>
              <td className="px-4 py-3 text-slate-400">{formatDateTime(row.local_updated_at)}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{JSON.stringify(row.record_payload_json)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
