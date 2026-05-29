import type { MarketplaceOrderResponse } from "../../../api/client";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

interface MarketplaceOrderTableProps {
  items: MarketplaceOrderResponse[];
  selectedOrderId: number | null;
  loading: boolean;
  onSelect: (orderId: number) => void;
}

export function MarketplaceOrderTable({
  items,
  selectedOrderId,
  loading,
  onSelect,
}: MarketplaceOrderTableProps): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Marketplace orders</h2>
          <p className="text-sm text-slate-400">Deterministically ordered by ordered date, newest first.</p>
        </div>
        <span className="text-xs uppercase tracking-[0.18em] text-slate-500">{items.length} loaded</span>
      </div>
      {loading ? <p className="mt-4 text-sm text-slate-400">Loading marketplace orders...</p> : null}
      {!loading && items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No marketplace orders imported yet.</p>
      ) : null}
      {!loading && items.length > 0 ? (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm text-slate-200">
            <thead className="text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="pb-3 pr-4">Order</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Total</th>
                <th className="pb-3 pr-4">Buyer</th>
                <th className="pb-3">Ordered</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const selected = selectedOrderId === item.id;
                return (
                  <tr
                    key={item.id}
                    className={selected ? "bg-cyan-500/10" : "hover:bg-white/5"}
                  >
                    <td className="py-3 pr-4">
                      <button
                        type="button"
                        onClick={() => onSelect(item.id)}
                        className="text-left font-medium text-cyan-100"
                      >
                        {item.marketplace_order_identifier}
                      </button>
                    </td>
                    <td className="py-3 pr-4 text-slate-300">{item.order_status}</td>
                    <td className="py-3 pr-4 text-slate-300">
                      {item.order_total} {item.order_currency}
                    </td>
                    <td className="py-3 pr-4 text-slate-400">{item.buyer_identifier ?? "Unknown"}</td>
                    <td className="py-3 text-slate-400">{formatDate(item.ordered_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
