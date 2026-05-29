import type { MarketplaceListingDraftDetailResponse } from "../../../api/client";
import { MarketplaceListingStatusBadge } from "./MarketplaceListingStatusBadge";
import { MarketplaceListingValidationErrors } from "./MarketplaceListingValidationErrors";

type Props = {
  detail: MarketplaceListingDraftDetailResponse | null;
  busy: boolean;
  canManage: boolean;
  onMarkReady: () => void;
  onGenerateProjection: () => void;
  onArchive: () => void;
};

export function MarketplaceListingDetailPanel({
  detail,
  busy,
  canManage,
  onMarkReady,
  onGenerateProjection,
  onArchive,
}: Props): JSX.Element {
  if (!detail) {
    return (
      <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-sm text-slate-500">
        Select a listing draft to inspect validation state and lineage.
      </div>
    );
  }
  const draft = detail.draft;
  return (
    <div className="space-y-4 rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Listing detail</p>
          <h3 className="mt-1 text-lg font-semibold text-white">{draft.listing_title}</h3>
          <p className="text-xs text-slate-500">
            Account #{draft.marketplace_account_id} · Inventory #{draft.inventory_item_id}
          </p>
        </div>
        <MarketplaceListingStatusBadge listingStatus={draft.listing_status} validationStatus={draft.validation_status} />
      </div>
      <MarketplaceListingValidationErrors errors={detail.validation_errors} />
      {canManage ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || draft.listing_status === "archived"}
            onClick={onMarkReady}
            className="rounded-xl border border-emerald-400/30 px-3 py-2 text-xs font-semibold text-emerald-100 disabled:opacity-50"
          >
            Mark ready
          </button>
          <button
            type="button"
            disabled={busy || draft.listing_status === "archived"}
            onClick={onGenerateProjection}
            className="rounded-xl border border-cyan-400/30 px-3 py-2 text-xs font-semibold text-cyan-100 disabled:opacity-50"
          >
            Generate projection
          </button>
          <button
            type="button"
            disabled={busy || draft.listing_status === "archived"}
            onClick={onArchive}
            className="rounded-xl border border-rose-400/30 px-3 py-2 text-xs font-semibold text-rose-100 disabled:opacity-50"
          >
            Archive draft
          </button>
        </div>
      ) : null}
      <div>
        <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Lineage</p>
        <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto text-xs text-slate-300">
          {detail.listing_events.map((event) => (
            <li key={event.id} className="font-mono">
              {event.event_type}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
