import type { MarketplaceInventoryDiagnosticsResponse, MarketplaceInventoryReconciliationReportResponse } from "../../../api/client";

type DiagnosticsProps = {
  diagnostics: MarketplaceInventoryDiagnosticsResponse;
};

export function MarketplaceSyncDiagnostics({ diagnostics }: DiagnosticsProps): JSX.Element {
  const cards = [
    ["Tracked states", String(diagnostics.total_states)],
    ["Pending", String(diagnostics.pending_states)],
    ["Failed states", String(diagnostics.failed_states)],
    ["Active conflicts", String(diagnostics.active_conflicts)],
    ["Completed runs", String(diagnostics.completed_runs)],
    ["Failed runs", String(diagnostics.failed_runs)],
  ];
  return (
    <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
      {cards.map(([label, value]) => (
        <div key={label} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
        </div>
      ))}
    </div>
  );
}

type Props = {
  report: MarketplaceInventoryReconciliationReportResponse | null;
};

export function MarketplaceReconciliationReportPanel({ report }: Props): JSX.Element {
  if (!report) {
    return (
      <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-sm text-slate-500">
        Trigger reconciliation to generate a deterministic report from the current sync state registry.
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Reconciliation report</p>
      <div className="mt-3 space-y-2">
        {report.entries.map((row) => (
          <div key={row.state_id} className="rounded-xl border border-white/5 bg-black/20 p-3 text-sm text-slate-200">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-xs text-slate-400">{row.marketplace_listing_identifier}</span>
              <span className="text-xs text-slate-400">Inventory #{row.inventory_item_id}</span>
            </div>
            <p className="mt-2 text-xs text-slate-300">
              Local {row.local_quantity} · Marketplace {row.marketplace_quantity}
            </p>
            <p className="mt-1 text-xs text-amber-200">
              {row.conflict_types.length ? row.conflict_types.join(", ") : "No active conflicts"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
