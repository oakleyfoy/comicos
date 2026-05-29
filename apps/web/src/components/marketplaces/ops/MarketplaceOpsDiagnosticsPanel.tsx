import type { MarketplaceOpsDiagnosticResponse } from "../../../api/client";
import { MarketplaceOpsStatusBadge } from "./MarketplaceOpsStatusBadge";

export function MarketplaceOpsDiagnosticsPanel({
  diagnostics,
}: {
  diagnostics: MarketplaceOpsDiagnosticResponse[];
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Diagnostics</p>
          <h2 className="mt-1 text-base font-semibold text-white">Marketplace diagnostics</h2>
        </div>
        <p className="text-sm text-slate-400">{diagnostics.length} visible</p>
      </div>
      {diagnostics.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No persisted diagnostics yet. Generate diagnostics to write the current rule evaluation to history.</p>
      ) : (
        <div className="mt-4 space-y-3">
          {diagnostics.map((row) => (
            <article key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-white">{row.diagnostic_code}</p>
                  <p className="mt-1 text-xs text-slate-500">{row.diagnostic_category}</p>
                </div>
                <MarketplaceOpsStatusBadge status={row.diagnostic_status} />
              </div>
              <p className="mt-3 text-sm text-slate-300">{row.diagnostic_message}</p>
              <pre className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-xs text-slate-200">
                {JSON.stringify(row.diagnostic_payload_json, null, 2)}
              </pre>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
