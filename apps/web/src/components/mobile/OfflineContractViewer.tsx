function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function OfflineContractViewer({
  items,
}: {
  items: import("../../api/client").OfflineSyncContractResponse[];
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No offline sync contracts yet.</p>;
  }
  return (
    <div className="space-y-3">
      {items.map((row) => (
        <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-white">
              {row.contract_type} <span className="font-mono text-xs text-slate-500">#{row.id}</span>
            </p>
            <p className="text-xs text-slate-500">{formatDateTime(row.created_at)}</p>
          </div>
          <pre className="mt-3 overflow-x-auto rounded-xl bg-black/40 p-3 text-xs text-slate-300">
            {JSON.stringify(row.contract_payload_json, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}
