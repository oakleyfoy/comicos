const STATUS_STYLES: Record<string, string> = {
  draft: "border-slate-500/30 bg-slate-500/10 text-slate-200",
  ready: "border-amber-400/30 bg-amber-500/10 text-amber-100",
  published_internal: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  unpublished_internal: "border-rose-400/30 bg-rose-500/10 text-rose-100",
  mapped: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  unmapped: "border-amber-400/30 bg-amber-500/10 text-amber-100",
  invalid: "border-rose-400/30 bg-rose-500/10 text-rose-100",
  pending: "border-sky-400/30 bg-sky-500/10 text-sky-100",
  completed: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  failed: "border-rose-400/30 bg-rose-500/10 text-rose-100",
};

export function ShopifyPublicationStatusBadge({ status }: { status: string }): JSX.Element {
  const style = STATUS_STYLES[status] ?? "border-white/10 bg-white/5 text-slate-300";
  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em] ${style}`}>
      {status}
    </span>
  );
}
