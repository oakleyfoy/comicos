export function ScanHistoryTable({
  items,
}: {
  items: import("../../../api/client").ScanCaptureResponse[];
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No scans captured yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="border-b border-white/10 bg-slate-950/60 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Value</th>
            <th className="px-4 py-3">Normalized</th>
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id} className="border-b border-white/5 last:border-0">
              <td className="px-4 py-3">{row.scan_type}</td>
              <td className="px-4 py-3 font-mono text-xs">{row.scan_value}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-400">{row.normalized_value}</td>
              <td className="px-4 py-3">{row.scan_status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
