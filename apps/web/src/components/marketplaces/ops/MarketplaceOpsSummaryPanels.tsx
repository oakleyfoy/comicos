export function MarketplaceOpsSummaryPanels({ summary }: { summary: Record<string, unknown> }): JSX.Element {
  const groups = [
    ["accounts", "Accounts"],
    ["listings", "Listings"],
    ["sync", "Sync"],
    ["orders", "Orders"],
    ["pricing", "Pricing"],
    ["events", "Events"],
    ["live_sales", "Live sales"],
  ] as const;

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Operational summary</p>
      <h2 className="mt-1 text-base font-semibold text-white">Marketplace ops summary panels</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {groups.map(([key, label]) => {
          const value = summary[key] as Record<string, unknown> | undefined;
          return (
            <article key={key} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
              <pre className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-xs text-slate-200">
                {JSON.stringify(value ?? {}, null, 2)}
              </pre>
            </article>
          );
        })}
      </div>
    </section>
  );
}
