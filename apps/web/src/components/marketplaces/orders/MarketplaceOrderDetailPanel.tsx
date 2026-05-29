import type { MarketplaceOrderDetailResponse } from "../../../api/client";

function formatDate(value?: string | null): string {
  if (!value) {
    return "—";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

interface MarketplaceOrderDetailPanelProps {
  detail: MarketplaceOrderDetailResponse | null;
}

export function MarketplaceOrderDetailPanel({ detail }: MarketplaceOrderDetailPanelProps): JSX.Element {
  if (!detail) {
    return (
      <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
        <h2 className="text-lg font-semibold text-white">Order detail</h2>
        <p className="mt-3 text-sm text-slate-400">Select an order to review its imported line items, transactions, and lineage.</p>
      </section>
    );
  }

  const { order, line_items: lineItems, events, import_summary: summary } = detail;

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">{order.marketplace_order_identifier}</h2>
          <p className="text-sm text-slate-400">
            {order.marketplace_type} order imported on {formatDate(order.imported_at)}
          </p>
        </div>
        <div className="rounded-2xl border border-cyan-400/20 px-3 py-2 text-right text-sm text-cyan-100">
          <div>{order.order_total} {order.order_currency}</div>
          <div className="text-xs uppercase tracking-[0.16em] text-cyan-300/80">{order.order_status}</div>
        </div>
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-3">
          <dt className="text-xs uppercase tracking-[0.16em] text-slate-500">Buyer</dt>
          <dd className="mt-1 text-sm text-slate-200">{order.buyer_identifier ?? "Unknown"}</dd>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-3">
          <dt className="text-xs uppercase tracking-[0.16em] text-slate-500">Ordered</dt>
          <dd className="mt-1 text-sm text-slate-200">{formatDate(order.ordered_at)}</dd>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-3">
          <dt className="text-xs uppercase tracking-[0.16em] text-slate-500">Imported line items</dt>
          <dd className="mt-1 text-sm text-slate-200">{summary.imported_line_items}</dd>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-3">
          <dt className="text-xs uppercase tracking-[0.16em] text-slate-500">Imported transactions</dt>
          <dd className="mt-1 text-sm text-slate-200">{summary.imported_transactions}</dd>
        </div>
      </dl>

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-white">Line items</h3>
        {lineItems.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">No line items were registered for this order.</p>
        ) : (
          <div className="mt-2 space-y-2">
            {lineItems.map((item) => (
              <div key={item.id} className="rounded-2xl border border-white/10 bg-slate-950/50 p-3 text-sm text-slate-200">
                <div className="flex items-center justify-between gap-3">
                  <span>{item.marketplace_listing_identifier}</span>
                  <span>{item.line_total}</span>
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  Qty {item.quantity} at {item.unit_price} {item.inventory_item_id ? `· Inventory #${item.inventory_item_id}` : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-white">Order lineage</h3>
        {events.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">No marketplace order events recorded yet.</p>
        ) : (
          <div className="mt-2 space-y-2">
            {events.map((event) => (
              <div key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-slate-100">{event.event_type}</span>
                  <span className="text-xs text-slate-500">{formatDate(event.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
