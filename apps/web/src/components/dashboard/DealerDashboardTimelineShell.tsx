import { EmptyState } from "../EmptyState";
import type { OrganizationDealerDashboardSnapshotResponse } from "../../api/client";
import { formatDateTime } from "./dealerDashboardLabels";

type Props = {
  snapshots: OrganizationDealerDashboardSnapshotResponse[];
};

export function DealerDashboardTimelineShell({ snapshots }: Props): JSX.Element {
  if (!snapshots.length) {
    return (
      <EmptyState
        title="No dashboard snapshots"
        description="Operational snapshots appear here after the dashboard refreshes from the backend aggregation layer."
      />
    );
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Operational timeline</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Dashboard snapshot lineage</h2>
        <p className="mt-1 text-sm text-slate-400">
          Append-only snapshot history with deterministic ordering (newest first). Live websocket updates are not enabled in this phase.
        </p>
      </div>
      <ol className="mt-4 space-y-3">
        {snapshots.map((snapshot) => (
          <li key={snapshot.id} className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-medium text-white">
                  Snapshot #{snapshot.id} · {snapshot.snapshot_type}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {Object.keys(snapshot.snapshot_payload_json ?? {}).length} payload keys · org {snapshot.organization_id}
                </p>
              </div>
              <time className="text-xs text-slate-400" dateTime={snapshot.generated_at}>
                {formatDateTime(snapshot.generated_at)}
              </time>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
