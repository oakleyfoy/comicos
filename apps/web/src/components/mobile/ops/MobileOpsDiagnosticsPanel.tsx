import type { MobileOpsDiagnosticResponse } from "../../../api/client";

export function MobileOpsDiagnosticsPanel({ diagnostics }: { diagnostics: MobileOpsDiagnosticResponse[] }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-lg font-semibold text-white">Diagnostics</h2>
      <div className="mt-4 space-y-3">
        {diagnostics.length === 0 ? <p className="text-sm text-slate-400">No diagnostics generated yet.</p> : null}
        {diagnostics.map((diagnostic) => (
          <div key={diagnostic.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">{diagnostic.diagnostic_code}</p>
              <span className="rounded-full border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.14em] text-slate-300">
                {diagnostic.diagnostic_status}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-300">{diagnostic.diagnostic_message}</p>
            <p className="mt-2 text-xs text-slate-500">{diagnostic.diagnostic_category}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
