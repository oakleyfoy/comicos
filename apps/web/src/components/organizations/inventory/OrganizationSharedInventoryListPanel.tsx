import type { InventoryItem, MarketplaceListingDraftResponse } from "../../../api/client";
import { MarketplaceListingStatusBadge } from "../../marketplaces/listings/MarketplaceListingStatusBadge";

type Props = {
  items: InventoryItem[];
  loading: boolean;
  organizationId?: number;
  listingDraftsByInventoryId?: Map<number, MarketplaceListingDraftResponse>;
  canCreateListing?: boolean;
  onCreateListingDraft?: (inventoryItemId: number) => void;
};

export function OrganizationSharedInventoryListPanel({
  items,
  loading,
  organizationId,
  listingDraftsByInventoryId,
  canCreateListing,
  onCreateListingDraft,
}: Props): JSX.Element {
  if (loading) {
    return <p className="text-sm text-slate-400">Loading shared inventory…</p>;
  }
  if (!items.length) {
    return <p className="text-sm text-slate-500">No organization-scoped inventory rows match the current filters.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="bg-slate-900/80 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Copy</th>
            <th className="px-4 py-3">Title</th>
            <th className="px-4 py-3">Assignment</th>
            <th className="px-4 py-3">Queue</th>
            <th className="px-4 py-3">Marketplace</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => {
            const listingDraft = listingDraftsByInventoryId?.get(row.inventory_copy_id);
            const marketplaceReady = listingDraft?.validation_status === "valid";
            return (
            <tr key={row.inventory_copy_id} className="border-t border-white/5">
              <td className="px-4 py-3 font-mono text-xs text-slate-400">#{row.inventory_copy_id}</td>
              <td className="px-4 py-3">
                <p className="font-medium text-white">{row.title}</p>
                <p className="text-xs text-slate-500">
                  {row.publisher} #{row.issue_number}
                </p>
              </td>
              <td className="px-4 py-3">
                {row.organization_assignment_status ? (
                  <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">
                    {row.organization_assignment_status} → user {row.organization_assigned_user_id}
                  </span>
                ) : (
                  <span className="text-xs text-slate-500">Unassigned</span>
                )}
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {row.organization_queue_name ? (
                  <>
                    {row.organization_queue_name}
                    {row.organization_queue_position ? ` · #${row.organization_queue_position}` : ""}
                  </>
                ) : (
                  "—"
                )}
                {row.organization_review_status ? (
                  <p className="mt-1 text-violet-300">
                    Review: {row.organization_review_status}
                    {row.organization_review_type ? ` (${row.organization_review_type})` : ""}
                  </p>
                ) : null}
              </td>
              <td className="px-4 py-3 text-xs">
                {listingDraft ? (
                  <div className="space-y-2">
                    <MarketplaceListingStatusBadge
                      listingStatus={listingDraft.listing_status}
                      validationStatus={listingDraft.validation_status}
                    />
                    <p className={marketplaceReady ? "text-emerald-300" : "text-amber-300"}>
                      {marketplaceReady ? "Marketplace-ready projection" : "Listing draft in progress"}
                    </p>
                    {organizationId ? (
                      <a
                        href={`/organizations/${organizationId}/marketplace-listings`}
                        className="font-semibold text-indigo-300 hover:text-indigo-200"
                      >
                        Listings workspace
                      </a>
                    ) : null}
                  </div>
                ) : canCreateListing ? (
                  <button
                    type="button"
                    className="rounded-lg border border-indigo-400/30 px-2 py-1 text-xs font-semibold text-indigo-100"
                    onClick={() => onCreateListingDraft?.(row.inventory_copy_id)}
                  >
                    Create listing draft
                  </button>
                ) : (
                  <span className="text-slate-500">No listing draft</span>
                )}
              </td>
            </tr>
          );})}
        </tbody>
      </table>
    </div>
  );
}
