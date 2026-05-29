function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function OfflineConflictViewer({
  items,
  canManage,
  busyConflictId,
  onAcknowledge,
}: {
  items: import("../../../api/client").OfflineSyncConflictResponse[];
  canManage: boolean;
  busyConflictId: number | null;
  onAcknowledge: (conflictId: number) => void;
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No sync conflicts tracked.</p>;
  }
  return (
    <div className="space-y-3">
      {items.map((row) => (
        <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-white">
              {row.conflict_type} <span className="text-slate-500">({row.conflict_status})</span>
            </p>
            <p className="text-xs text-slate-500">{formatDateTime(row.created_at)}</p>
          </div>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <pre className="overflow-x-auto rounded-xl bg-black/40 p-3 text-xs text-slate-300">
              local: {JSON.stringify(row.local_payload_json, null, 2)}
            </pre>
            <pre className="overflow-x-auto rounded-xl bg-black/40 p-3 text-xs text-slate-300">
              server: {JSON.stringify(row.server_payload_json, null, 2)}
            </pre>
          </div>
          {canManage && row.conflict_status === "open" ? (
            <button
              type="button"
              disabled={busyConflictId === row.id}
              onClick={() => onAcknowledge(row.id)}
              className="mt-3 rounded-xl border border-amber-400/40 px-3 py-1.5 text-xs font-semibold text-amber-100 disabled:opacity-50"
            >
              Acknowledge conflict
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
