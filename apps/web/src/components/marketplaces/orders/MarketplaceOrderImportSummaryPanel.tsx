import type { FormEvent } from "react";

import type { MarketplaceAccountResponse, MarketplaceOrderDetailResponse } from "../../../api/client";

interface MarketplaceOrderImportSummaryPanelProps {
  accounts: MarketplaceAccountResponse[];
  canManage: boolean;
  submitting: boolean;
  detail: MarketplaceOrderDetailResponse | null;
  onSubmit: (payload: {
    marketplace_account_id: number;
    marketplace_order_identifier: string;
    buyer_identifier?: string | null;
    order_total: string;
    order_currency: string;
    ordered_at?: string | null;
    marketplace_listing_identifier: string;
    transaction_reference: string;
    fee_amount: string;
  }) => Promise<void>;
}

export function MarketplaceOrderImportSummaryPanel({
  accounts,
  canManage,
  submitting,
  detail,
  onSubmit,
}: MarketplaceOrderImportSummaryPanelProps): JSX.Element {
  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const marketplaceAccountId = Number(form.get("marketplace_account_id"));
    await onSubmit({
      marketplace_account_id: marketplaceAccountId,
      marketplace_order_identifier: String(form.get("marketplace_order_identifier") || ""),
      buyer_identifier: String(form.get("buyer_identifier") || "") || null,
      order_total: String(form.get("order_total") || "0"),
      order_currency: String(form.get("order_currency") || "USD"),
      ordered_at: String(form.get("ordered_at") || "") || null,
      marketplace_listing_identifier: String(form.get("marketplace_listing_identifier") || ""),
      transaction_reference: String(form.get("transaction_reference") || ""),
      fee_amount: String(form.get("fee_amount") || "0.00"),
    });
    event.currentTarget.reset();
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-lg font-semibold text-white">Order import shell</h2>
      <p className="text-sm text-slate-400">Manual import for deterministic ingestion testing. No marketplace API calls are made.</p>

      {detail ? (
        <div className="mt-4 rounded-2xl border border-emerald-400/20 bg-emerald-950/20 p-3 text-sm text-emerald-50">
          <div className="font-medium">Last import summary</div>
          <div className="mt-1">
            Order #{detail.import_summary.order_id} · {detail.import_summary.imported_line_items} line items ·{" "}
            {detail.import_summary.imported_transactions} transactions
          </div>
          <div className="mt-1 text-emerald-200/80">
            Duplicate detected: {detail.import_summary.duplicate_detected ? "yes" : "no"}
          </div>
        </div>
      ) : null}

      {!canManage ? (
        <p className="mt-4 text-sm text-slate-400">Members with `organization:update` can import marketplace orders.</p>
      ) : null}
      {canManage && accounts.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">Connect a marketplace account before importing orders.</p>
      ) : null}
      {canManage && accounts.length > 0 ? (
        <form className="mt-4 grid gap-3" onSubmit={(event) => void handleSubmit(event)}>
          <label className="grid gap-1 text-sm text-slate-300">
            Marketplace account
            <select
              name="marketplace_account_id"
              className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
              defaultValue={String(accounts[0].id)}
            >
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm text-slate-300">
            Marketplace order identifier
            <input
              name="marketplace_order_identifier"
              required
              className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
              placeholder="ebay-order-1001"
            />
          </label>
          <label className="grid gap-1 text-sm text-slate-300">
            Buyer identifier
            <input
              name="buyer_identifier"
              className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
              placeholder="buyer-123"
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm text-slate-300">
              Order total
              <input
                name="order_total"
                required
                defaultValue="19.99"
                className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="grid gap-1 text-sm text-slate-300">
              Fee amount
              <input
                name="fee_amount"
                required
                defaultValue="1.99"
                className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
              />
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm text-slate-300">
              Currency
              <input
                name="order_currency"
                defaultValue="USD"
                className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm uppercase text-white"
              />
            </label>
            <label className="grid gap-1 text-sm text-slate-300">
              Ordered at
              <input
                name="ordered_at"
                type="datetime-local"
                className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
              />
            </label>
          </div>
          <label className="grid gap-1 text-sm text-slate-300">
            Marketplace listing identifier
            <input
              name="marketplace_listing_identifier"
              required
              placeholder="ebay:listing-1001"
              className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
            />
          </label>
          <label className="grid gap-1 text-sm text-slate-300">
            Transaction reference
            <input
              name="transaction_reference"
              required
              placeholder="txn-1001"
              className="rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
          >
            {submitting ? "Importing..." : "Import order"}
          </button>
        </form>
      ) : null}
    </section>
  );
}
