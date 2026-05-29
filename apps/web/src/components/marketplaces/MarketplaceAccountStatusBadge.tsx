export function MarketplaceAccountStatusBadge({ status }: { status: string }): JSX.Element {
  const normalized = status.toLowerCase();
  const tone =
    normalized === "connected"
      ? "border-emerald-400/35 bg-emerald-400/10 text-emerald-100"
      : normalized === "suspended"
        ? "border-amber-400/35 bg-amber-400/10 text-amber-100"
        : "border-slate-400/35 bg-slate-400/10 text-slate-200";

  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${tone}`}>{normalized}</span>;
}
