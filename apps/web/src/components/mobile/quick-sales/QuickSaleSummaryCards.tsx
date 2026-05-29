export function QuickSaleSummaryCards({
  sales,
}: {
  sales: import("../../../api/client").QuickSaleResponse[];
}): JSX.Element {
  const draftCount = sales.filter((sale) => sale.sale_status === "draft").length;
  const completedCount = sales.filter((sale) => sale.sale_status === "completed").length;
  const totalSales = sales.reduce((sum, sale) => sum + Number(sale.total_amount), 0);
  const cards = [
    { label: "Sales", value: String(sales.length) },
    { label: "Draft", value: String(draftCount) },
    { label: "Completed", value: String(completedCount) },
    { label: "Volume", value: `$${totalSales.toFixed(2)}` },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{card.label}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{card.value}</p>
        </div>
      ))}
    </div>
  );
}
