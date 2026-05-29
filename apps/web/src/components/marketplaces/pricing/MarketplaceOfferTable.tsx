import type { MarketplaceOfferResponse } from "../../../api/client";

export function MarketplaceOfferTable({
  items,
  busyOfferId,
  canManage,
  onUpdateStatus,
}: {
  items: MarketplaceOfferResponse[];
  busyOfferId: number | null;
  canManage: boolean;
  onUpdateStatus: (offerId: number, offerStatus: "reviewed" | "accepted_internal" | "rejected_internal" | "expired") => Promise<void>;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Offers</p>
          <h2 className="mt-1 text-base font-semibold text-white">Internal offer tracking</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No offers have been ingested yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Offer</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Timing</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr key={item.id} className="bg-slate-950/35 align-top text-slate-200">
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{item.marketplace_offer_identifier}</p>
                    <p className="mt-1 text-xs text-slate-500">Listing draft #{item.marketplace_listing_draft_id}</p>
                    <p className="text-xs text-slate-500">{item.buyer_identifier ?? "Unknown buyer"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-lg font-semibold text-white">
                      {item.offer_currency} {item.offer_amount}
                    </p>
                    <p className="text-xs text-slate-500">Received as replay-safe internal record</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    <p>Received: {new Date(item.received_at).toLocaleString()}</p>
                    <p>Expires: {item.expires_at ? new Date(item.expires_at).toLocaleString() : "n/a"}</p>
                    <p>Created: {new Date(item.created_at).toLocaleString()}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                      {item.offer_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {canManage ? (
                      <div className="flex flex-wrap gap-2">
                        <ActionButton disabled={busyOfferId === item.id} onClick={() => void onUpdateStatus(item.id, "reviewed")}>
                          Review
                        </ActionButton>
                        <ActionButton
                          disabled={busyOfferId === item.id}
                          onClick={() => void onUpdateStatus(item.id, "accepted_internal")}
                        >
                          Accept internal
                        </ActionButton>
                        <ActionButton
                          disabled={busyOfferId === item.id}
                          onClick={() => void onUpdateStatus(item.id, "rejected_internal")}
                        >
                          Reject internal
                        </ActionButton>
                        <ActionButton disabled={busyOfferId === item.id} onClick={() => void onUpdateStatus(item.id, "expired")}>
                          Expire
                        </ActionButton>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">View only</p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ActionButton({
  children,
  disabled,
  onClick,
}: {
  children: string;
  disabled: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-2xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}
