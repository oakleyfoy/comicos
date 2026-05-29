export function QuickSaleListPanel({
  items,
  selectedSaleId,
  onSelect,
}: {
  items: import("../../../api/client").QuickSaleResponse[];
  selectedSaleId: number | null;
  onSelect: (saleId: number) => void;
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No quick sales recorded yet.</p>;
  }
  return (
    <div className="space-y-2">
      {items.map((sale) => (
        <button
          key={sale.id}
          type="button"
          onClick={() => onSelect(sale.id)}
          className={`w-full rounded-2xl border px-4 py-3 text-left ${
            selectedSaleId === sale.id ? "border-cyan-400/40 bg-cyan-400/5" : "border-white/10 bg-slate-950/40"
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">{sale.sale_identifier}</p>
              <p className="text-xs text-slate-500">{sale.sale_source}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-slate-200">${sale.total_amount}</p>
              <p className="text-xs text-slate-500">{sale.sale_status}</p>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
