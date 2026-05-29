import type { MarketplaceTransactionReconciliationReportResponse } from "../../../api/client";
import { MarketplaceTransactionMismatchList } from "./MarketplaceTransactionMismatchList";

interface MarketplaceReconciliationReportViewerProps {
  report: MarketplaceTransactionReconciliationReportResponse | null;
}

export function MarketplaceReconciliationReportViewer({
  report,
}: MarketplaceReconciliationReportViewerProps): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-lg font-semibold text-white">Reconciliation report</h2>
      <p className="text-sm text-slate-400">Deterministic mismatch detection across imported orders and transactions.</p>
      {!report ? (
        <p className="mt-4 text-sm text-slate-400">No reconciliation report generated yet.</p>
      ) : (
        <div className="mt-4 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-3">
              <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Orders scanned</div>
              <div className="mt-1 text-lg font-semibold text-white">{report.total_orders}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-3">
              <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Transactions scanned</div>
              <div className="mt-1 text-lg font-semibold text-white">{report.total_transactions}</div>
            </div>
          </div>
          <MarketplaceTransactionMismatchList mismatches={report.mismatches} />
        </div>
      )}
    </section>
  );
}
