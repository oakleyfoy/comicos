import type { MarketplaceEventDetailResponse } from "../../../api/client";
import { MarketplaceEventStatusBadge } from "./MarketplaceEventStatusBadge";
import { MarketplaceEventValidationErrors } from "./MarketplaceEventValidationErrors";

export function MarketplaceEventDetailPanel({
  detail,
  canManage,
  busy,
  onProcess,
}: {
  detail: MarketplaceEventDetailResponse | null;
  canManage: boolean;
  busy: boolean;
  onProcess: (eventId: number) => Promise<void>;
}): JSX.Element {
  if (!detail) {
    return (
      <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-400">
        Select an event to see details, lineage, and processing state.
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Event detail</p>
          <h2 className="mt-1 text-base font-semibold text-white">Event #{detail.event.id}</h2>
          <p className="mt-1 text-sm text-slate-400">{detail.event.external_event_identifier}</p>
        </div>
        <MarketplaceEventStatusBadge status={detail.event.event_status} />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Metric label="Marketplace type" value={detail.event.marketplace_type} />
        <Metric label="Event type" value={detail.event.event_type} />
        <Metric label="Received" value={new Date(detail.event.received_at).toLocaleString()} />
        <Metric label="Processed" value={detail.event.processed_at ? new Date(detail.event.processed_at).toLocaleString() : "n/a"} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!canManage || busy}
          onClick={() => void onProcess(detail.event.id)}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Processing..." : "Process event"}
        </button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[0.9fr,1.1fr]">
        <MarketplaceEventValidationErrors errors={detail.validation_errors} />
        <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Payload</p>
          <pre className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/70 p-3 text-xs text-slate-300">
            {JSON.stringify(detail.event.event_payload_json, null, 2)}
          </pre>
        </section>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
    </div>
  );
}
