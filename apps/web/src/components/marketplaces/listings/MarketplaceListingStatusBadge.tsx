type Props = {
  listingStatus: string;
  validationStatus: string;
};

export function MarketplaceListingStatusBadge({ listingStatus, validationStatus }: Props): JSX.Element {
  const listingTone =
    listingStatus === "archived"
      ? "bg-slate-500/15 text-slate-300"
      : listingStatus === "ready"
        ? "bg-emerald-500/15 text-emerald-200"
        : "bg-amber-500/15 text-amber-200";
  const validationTone =
    validationStatus === "valid"
      ? "bg-cyan-500/15 text-cyan-200"
      : validationStatus === "invalid"
        ? "bg-rose-500/15 text-rose-200"
        : "bg-violet-500/15 text-violet-200";
  return (
    <div className="flex flex-wrap gap-2">
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${listingTone}`}>{listingStatus}</span>
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${validationTone}`}>{validationStatus}</span>
    </div>
  );
}
