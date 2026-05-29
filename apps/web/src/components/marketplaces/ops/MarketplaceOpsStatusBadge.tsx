const STATUS_STYLES: Record<string, string> = {
  ok: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  warning: "border-amber-400/30 bg-amber-500/10 text-amber-100",
  error: "border-rose-400/30 bg-rose-500/10 text-rose-100",
  generated: "border-sky-400/30 bg-sky-500/10 text-sky-100",
  accessed: "border-slate-400/30 bg-slate-500/10 text-slate-200",
};

export function MarketplaceOpsStatusBadge({ status }: { status: string }): JSX.Element {
  const style = STATUS_STYLES[status] ?? "border-white/10 bg-white/5 text-slate-300";
  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em] ${style}`}>
      {status}
    </span>
  );
}
