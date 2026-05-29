export function MarketplaceAnalyticsSummaryCards({ summary }: { summary: Record<string, unknown> }): JSX.Element {
  const cards = [
    { label: "Accounts", value: JSON.stringify(summary["accounts"] ?? {}) },
    { label: "Listings", value: JSON.stringify(summary["listings"] ?? {}) },
    { label: "Orders", value: JSON.stringify(summary["orders"] ?? {}) },
    { label: "Transactions", value: JSON.stringify(summary["transactions"] ?? {}) },
    { label: "Pricing", value: JSON.stringify(summary["pricing"] ?? {}) },
    { label: "Events", value: JSON.stringify(summary["events"] ?? {}) },
    { label: "Live sales", value: JSON.stringify(summary["live_sales"] ?? {}) },
    { label: "Shopify", value: JSON.stringify(summary["shopify"] ?? {}) },
  ];

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Performance summary</p>
      <h2 className="mt-1 text-base font-semibold text-white">Analytics performance summary cards</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <article key={card.label} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{card.label}</p>
            <pre className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-xs text-slate-200">
              {card.value}
            </pre>
          </article>
        ))}
      </div>
    </section>
  );
}
