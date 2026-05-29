import { Link } from "react-router-dom";

import type { MarketplaceListingDraftResponse } from "../../../api/client";
import { MarketplaceListingStatusBadge } from "./MarketplaceListingStatusBadge";

type Props = {
  organizationId: number;
  items: MarketplaceListingDraftResponse[];
  selectedListingId: number | null;
  onSelect: (listingId: number) => void;
  loading: boolean;
};

export function MarketplaceListingDraftTable({
  organizationId,
  items,
  selectedListingId,
  onSelect,
  loading,
}: Props): JSX.Element {
  if (loading) {
    return <p className="text-sm text-slate-400">Loading listing drafts…</p>;
  }
  if (!items.length) {
    return <p className="text-sm text-slate-500">No marketplace listing drafts yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="bg-slate-900/80 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Title</th>
            <th className="px-4 py-3">Inventory</th>
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr
              key={row.id}
              className={`border-t border-white/5 cursor-pointer ${selectedListingId === row.id ? "bg-indigo-500/10" : "hover:bg-white/5"}`}
              onClick={() => onSelect(row.id)}
            >
              <td className="px-4 py-3">
                <p className="font-medium text-white">{row.listing_title}</p>
                <p className="text-xs text-slate-500">Draft #{row.id}</p>
              </td>
              <td className="px-4 py-3 font-mono text-xs text-slate-400">#{row.inventory_item_id}</td>
              <td className="px-4 py-3">
                <MarketplaceListingStatusBadge listingStatus={row.listing_status} validationStatus={row.validation_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-white/5 px-4 py-2 text-xs text-slate-500">
        Organization {organizationId} · deterministic created_at ordering
      </p>
    </div>
  );
}

export function MarketplaceListingsPageLink({ organizationId }: { organizationId: number }): JSX.Element {
  return (
    <Link
      to={`/organizations/${organizationId}/marketplace-listings`}
      className="text-xs font-semibold text-indigo-300 hover:text-indigo-200"
    >
      Open marketplace listings
    </Link>
  );
}
