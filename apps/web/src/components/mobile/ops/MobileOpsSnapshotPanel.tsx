import type { MobileOpsSnapshotResponse } from "../../../api/client";

export function MobileOpsSnapshotPanel({ snapshot }: { snapshot: MobileOpsSnapshotResponse | null }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-lg font-semibold text-white">Latest Snapshot</h2>
      {!snapshot ? <p className="mt-4 text-sm text-slate-400">No snapshot generated yet.</p> : null}
      {snapshot ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <p className="text-sm font-semibold text-white">{snapshot.snapshot_type}</p>
            <p className="mt-2 text-xs text-slate-500">Snapshot #{snapshot.id}</p>
          </div>
          <pre className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-xs text-slate-300">
            {JSON.stringify(snapshot.snapshot_payload_json, null, 2)}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
