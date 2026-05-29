import type { MarketplacePriceRecommendationResponse } from "../../../api/client";

export function MarketplacePriceRecommendationTable({
  items,
  busyRecommendationId,
  canManage,
  onReview,
}: {
  items: MarketplacePriceRecommendationResponse[];
  busyRecommendationId: number | null;
  canManage: boolean;
  onReview: (recommendationId: number, recommendationStatus: "reviewed" | "applied_internal" | "dismissed") => Promise<void>;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Recommendations</p>
          <h2 className="mt-1 text-base font-semibold text-white">Deterministic price suggestions</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No price recommendations have been generated yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Listing</th>
                <th className="px-4 py-3">Recommendation</th>
                <th className="px-4 py-3">Bounds</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr key={item.id} className="bg-slate-950/35 align-top text-slate-200">
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{item.recommendation_type}</p>
                    <p className="mt-1 text-xs text-slate-500">Listing draft #{item.marketplace_listing_draft_id}</p>
                    <p className="text-xs text-slate-500">Inventory #{item.inventory_item_id}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-lg font-semibold text-white">${item.recommended_price}</p>
                    <p className="mt-1 text-xs text-slate-500">Current {item.current_listing_price ?? "n/a"}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.recommendation_reason}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    <p>Floor: {item.floor_price ?? "n/a"}</p>
                    <p>Ceiling: {item.ceiling_price ?? "n/a"}</p>
                    <p>Generated: {new Date(item.generated_at).toLocaleString()}</p>
                    <p>Reviewed: {item.reviewed_at ? new Date(item.reviewed_at).toLocaleString() : "n/a"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                      {item.recommendation_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {canManage ? (
                      <div className="flex flex-wrap gap-2">
                        <ActionButton
                          disabled={busyRecommendationId === item.id}
                          onClick={() => void onReview(item.id, "reviewed")}
                        >
                          Review
                        </ActionButton>
                        <ActionButton
                          disabled={busyRecommendationId === item.id}
                          onClick={() => void onReview(item.id, "applied_internal")}
                        >
                          Apply internal
                        </ActionButton>
                        <ActionButton
                          disabled={busyRecommendationId === item.id}
                          onClick={() => void onReview(item.id, "dismissed")}
                        >
                          Dismiss
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
