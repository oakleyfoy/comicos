import type { MarketplaceAnalyticsSnapshotResponse } from "../../../api/client";
import { MarketplaceAnalyticsStatusBadge } from "./MarketplaceAnalyticsStatusBadge";

export function MarketplaceAnalyticsSnapshotPanel({
  snapshot,
}: {
  snapshot: MarketplaceAnalyticsSnapshotResponse | null;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Latest snapshot</p>
          <h2 className="mt-1 text-base font-semibold text-white">Analytics snapshot viewer</h2>
        </div>
        <MarketplaceAnalyticsStatusBadge status={snapshot ? "generated" : "summary"} />
      </div>
      {snapshot ? (
        <pre className="mt-4 max-h-[28rem] overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-xs text-slate-200">
          {JSON.stringify(snapshot.snapshot_payload_json, null, 2)}
        </pre>
      ) : (
        <p className="mt-4 text-sm text-slate-400">Generate an analytics snapshot to persist the current performance payload.</p>
      )}
    </section>
  );
}
