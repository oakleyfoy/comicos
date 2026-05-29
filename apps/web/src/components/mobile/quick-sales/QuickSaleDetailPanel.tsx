export function QuickSaleDetailPanel({
  detail,
  canManage,
  submitting,
  inventoryItemId,
  unitPrice,
  discountAmount,
  paymentMethod,
  paymentAmount,
  onInventoryItemIdChange,
  onUnitPriceChange,
  onDiscountAmountChange,
  onPaymentMethodChange,
  onPaymentAmountChange,
  onAddLineItem,
  onRemoveLineItem,
  onRecordPayment,
  onComplete,
  onVoid,
}: {
  detail: import("../../../api/client").QuickSaleDetailResponse | null;
  canManage: boolean;
  submitting: boolean;
  inventoryItemId: string;
  unitPrice: string;
  discountAmount: string;
  paymentMethod: string;
  paymentAmount: string;
  onInventoryItemIdChange: (value: string) => void;
  onUnitPriceChange: (value: string) => void;
  onDiscountAmountChange: (value: string) => void;
  onPaymentMethodChange: (value: string) => void;
  onPaymentAmountChange: (value: string) => void;
  onAddLineItem: () => void;
  onRemoveLineItem: (lineItemId: number) => void;
  onRecordPayment: () => void;
  onComplete: () => void;
  onVoid: () => void;
}): JSX.Element {
  if (!detail) {
    return <p className="text-sm text-slate-400">Select a sale to inspect line items, payments, and events.</p>;
  }

  const { sale, line_items: lineItems, payments } = detail;
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-lg font-semibold text-white">{sale.sale_identifier}</p>
            <p className="text-sm text-slate-400">
              {sale.sale_source} · {sale.sale_status}
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-slate-500">Total</p>
            <p className="text-2xl font-semibold text-white">${sale.total_amount}</p>
          </div>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-white/10 px-3 py-2">
            <p className="text-xs text-slate-500">Subtotal</p>
            <p className="text-sm text-white">${sale.subtotal_amount}</p>
          </div>
          <div className="rounded-xl border border-white/10 px-3 py-2">
            <p className="text-xs text-slate-500">Discount</p>
            <p className="text-sm text-white">${sale.discount_amount}</p>
          </div>
          <div className="rounded-xl border border-white/10 px-3 py-2">
            <p className="text-xs text-slate-500">Buyer</p>
            <p className="text-sm text-white">{sale.buyer_label || "Walk-up"}</p>
          </div>
        </div>
      </div>

      {canManage && sale.sale_status === "draft" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <p className="text-sm font-semibold text-white">Line item editor</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <input
                value={inventoryItemId}
                onChange={(e) => onInventoryItemIdChange(e.target.value)}
                placeholder="Inventory item id"
                className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              />
              <input
                value={unitPrice}
                onChange={(e) => onUnitPriceChange(e.target.value)}
                placeholder="Unit price"
                className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              />
              <input
                value={discountAmount}
                onChange={(e) => onDiscountAmountChange(e.target.value)}
                placeholder="Discount"
                className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              />
              <button
                type="button"
                disabled={submitting || !inventoryItemId.trim() || !unitPrice.trim()}
                onClick={onAddLineItem}
                className="rounded-xl border border-cyan-400/40 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
              >
                Add line item
              </button>
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <p className="text-sm font-semibold text-white">Payment recorder</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <select
                value={paymentMethod}
                onChange={(e) => onPaymentMethodChange(e.target.value)}
                className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                <option value="cash">cash</option>
                <option value="card_external">card_external</option>
                <option value="venmo_external">venmo_external</option>
                <option value="paypal_external">paypal_external</option>
                <option value="other_external">other_external</option>
              </select>
              <input
                value={paymentAmount}
                onChange={(e) => onPaymentAmountChange(e.target.value)}
                placeholder="Payment amount"
                className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              />
              <button
                type="button"
                disabled={submitting || !paymentAmount.trim()}
                onClick={onRecordPayment}
                className="rounded-xl border border-emerald-400/40 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:opacity-50"
              >
                Record payment
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
        <p className="text-sm font-semibold text-white">Line items</p>
        {lineItems.length === 0 ? <p className="mt-2 text-sm text-slate-400">No line items yet.</p> : null}
        <div className="mt-3 space-y-2">
          {lineItems.map((line) => (
            <div key={line.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 px-3 py-2">
              <div>
                <p className="text-sm text-white">Inventory #{line.inventory_item_id ?? "?"}</p>
                <p className="text-xs text-slate-500">
                  ${line.unit_price} - ${line.discount_amount} = ${line.line_total} · {line.line_status}
                </p>
              </div>
              {canManage && sale.sale_status === "draft" && line.line_status === "added" ? (
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => onRemoveLineItem(line.id)}
                  className="text-xs text-rose-200 underline disabled:opacity-50"
                >
                  Remove
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
        <p className="text-sm font-semibold text-white">Payments</p>
        {payments.length === 0 ? <p className="mt-2 text-sm text-slate-400">No payments recorded yet.</p> : null}
        <div className="mt-3 space-y-2">
          {payments.map((payment) => (
            <div key={payment.id} className="rounded-xl border border-white/10 px-3 py-2 text-sm text-slate-200">
              {payment.payment_method} · ${payment.amount} · {payment.payment_status}
            </div>
          ))}
        </div>
      </div>

      {canManage && sale.sale_status === "draft" ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={submitting}
            onClick={onComplete}
            className="rounded-xl border border-emerald-400/40 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:opacity-50"
          >
            Complete sale
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={onVoid}
            className="rounded-xl border border-rose-400/40 px-4 py-2 text-sm font-semibold text-rose-100 disabled:opacity-50"
          >
            Void sale
          </button>
        </div>
      ) : null}
    </div>
  );
}
