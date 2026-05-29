export function IntakeStagingViewer({
  items,
  canManage,
  busyStagingId,
  onApprove,
  onArchive,
}: {
  items: import("../../../api/client").IntakeStagingRecordResponse[];
  canManage: boolean;
  busyStagingId: number | null;
  onApprove: (stagingId: number) => void;
  onArchive: (stagingId: number) => void;
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No intake staging records.</p>;
  }
  return (
    <div className="space-y-3">
      {items.map((row) => (
        <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-sm font-semibold text-white">
            Staging #{row.id} <span className="text-slate-500">({row.staging_status})</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">Scan capture #{row.scan_capture_id}</p>
          {canManage && row.staging_status === "pending" ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busyStagingId === row.id}
                onClick={() => onApprove(row.id)}
                className="rounded-xl border border-emerald-400/40 px-3 py-1.5 text-xs font-semibold text-emerald-100 disabled:opacity-50"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={busyStagingId === row.id}
                onClick={() => onArchive(row.id)}
                className="rounded-xl border border-slate-400/40 px-3 py-1.5 text-xs text-slate-200 disabled:opacity-50"
              >
                Archive
              </button>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
