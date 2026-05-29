export function MarketplaceVerificationStatusBadge({ status }: { status: string }): JSX.Element {
  const normalized = status.toLowerCase();
  const tone =
    normalized === "verified"
      ? "border-cyan-400/35 bg-cyan-400/10 text-cyan-100"
      : normalized === "failed"
        ? "border-rose-400/35 bg-rose-400/10 text-rose-100"
        : "border-amber-400/35 bg-amber-400/10 text-amber-100";

  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${tone}`}>{normalized}</span>;
}
