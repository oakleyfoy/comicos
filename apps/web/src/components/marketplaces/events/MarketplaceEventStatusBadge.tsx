export function MarketplaceEventStatusBadge({
  status,
}: {
  status: string;
}): JSX.Element {
  const tone =
    status === "processed"
      ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100"
      : status === "validated"
        ? "border-sky-400/30 bg-sky-500/10 text-sky-100"
        : status === "failed"
          ? "border-rose-400/30 bg-rose-500/10 text-rose-100"
          : "border-white/10 bg-white/5 text-slate-300";

  return (
    <span className={`rounded-full border px-3 py-1 text-xs uppercase tracking-[0.16em] ${tone}`}>
      {status}
    </span>
  );
}
