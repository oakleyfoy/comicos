import type { MarketplaceTransactionMismatchResponse } from "../../../api/client";

interface MarketplaceTransactionMismatchListProps {
  mismatches: MarketplaceTransactionMismatchResponse[];
}

export function MarketplaceTransactionMismatchList({
  mismatches,
}: MarketplaceTransactionMismatchListProps): JSX.Element {
  if (mismatches.length === 0) {
    return <p className="text-sm text-slate-400">No transaction mismatches detected.</p>;
  }

  return (
    <div className="space-y-2">
      {mismatches.map((mismatch, index) => (
        <div key={`${mismatch.order_id}-${mismatch.mismatch_code}-${index}`} className="rounded-2xl border border-amber-400/20 bg-amber-950/20 p-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium text-amber-100">{mismatch.mismatch_code}</span>
            <span className="text-xs text-amber-200/80">Order #{mismatch.order_id}</span>
          </div>
          <p className="mt-1 text-sm text-amber-50/90">{mismatch.message}</p>
          {mismatch.transaction_references.length > 0 ? (
            <p className="mt-1 text-xs text-amber-200/80">
              References: {mismatch.transaction_references.join(", ")}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
