const STATUS_STYLES: Record<string, string> = {
  generated: "border-sky-400/30 bg-sky-500/10 text-sky-100",
  current: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  summary: "border-white/10 bg-white/5 text-slate-300",
  trend: "border-violet-400/30 bg-violet-500/10 text-violet-100",
};

export function MarketplaceAnalyticsStatusBadge({ status }: { status: string }): JSX.Element {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.summary;
  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em] ${style}`}>
      {status}
    </span>
  );
}
