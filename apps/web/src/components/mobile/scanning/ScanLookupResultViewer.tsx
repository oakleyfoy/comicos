export function ScanLookupResultViewer({
  items,
}: {
  items: import("../../../api/client").ScanLookupResultResponse[];
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No lookup results.</p>;
  }
  return (
    <div className="space-y-3">
      {items.map((row) => (
        <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-sm font-semibold text-white">
            {row.lookup_type} <span className="font-mono text-xs text-slate-500">capture #{row.scan_capture_id}</span>
          </p>
          <pre className="mt-2 overflow-x-auto rounded-xl bg-black/40 p-3 text-xs text-slate-300">
            {JSON.stringify(row.lookup_payload_json, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}
