import type { MobileAnalyticsSnapshotResponse } from "../../../api/client";

export function MobileAnalyticsSnapshotViewer({ snapshot }: { snapshot: MobileAnalyticsSnapshotResponse | null }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <h2 className="text-lg font-semibold text-white">Latest snapshot</h2>
        <p className="mt-1 text-sm text-slate-400">Backend-authored analytics snapshot payload for replay-safe inspection.</p>
      </div>
      {snapshot ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <p className="text-sm font-semibold text-white">{snapshot.snapshot_type}</p>
            <p className="mt-1 text-xs text-slate-500">{new Date(snapshot.generated_at).toLocaleString()}</p>
          </div>
          <pre className="overflow-x-auto rounded-2xl bg-slate-950/80 p-4 text-xs text-slate-300">
            {JSON.stringify(snapshot.snapshot_payload_json, null, 2)}
          </pre>
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-400">No analytics snapshot generated yet.</p>
      )}
    </section>
  );
}
