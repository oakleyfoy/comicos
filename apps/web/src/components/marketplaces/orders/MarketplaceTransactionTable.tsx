import type { MarketplaceTransactionResponse } from "../../../api/client";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

interface MarketplaceTransactionTableProps {
  items: MarketplaceTransactionResponse[];
}

export function MarketplaceTransactionTable({ items }: MarketplaceTransactionTableProps): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Transactions</h2>
          <p className="text-sm text-slate-400">Backend-authored transaction registry for imported marketplace orders.</p>
        </div>
        <span className="text-xs uppercase tracking-[0.16em] text-slate-500">{items.length} shown</span>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No transactions imported yet.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm text-slate-200">
            <thead className="text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="pb-3 pr-4">Reference</th>
                <th className="pb-3 pr-4">Type</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Gross / Fee / Net</th>
                <th className="pb-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-white/5">
                  <td className="py-3 pr-4 text-cyan-100">{item.transaction_reference}</td>
                  <td className="py-3 pr-4 text-slate-300">{item.transaction_type}</td>
                  <td className="py-3 pr-4 text-slate-300">{item.transaction_status}</td>
                  <td className="py-3 pr-4 text-slate-400">
                    {item.gross_amount} / {item.fee_amount} / {item.net_amount} {item.transaction_currency}
                  </td>
                  <td className="py-3 text-slate-400">{formatDate(item.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
