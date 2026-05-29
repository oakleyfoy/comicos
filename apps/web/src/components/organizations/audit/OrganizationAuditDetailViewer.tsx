import { EmptyState } from "../../EmptyState";
import type { OrganizationAuditLedgerResponse } from "../../../api/client";

export function OrganizationAuditDetailViewer({ entry }: { entry: OrganizationAuditLedgerResponse | null }): JSX.Element {
  if (!entry) {
    return <EmptyState title="No audit detail selected" description="Select an audit row to inspect its immutable payload." />;
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Detail viewer</p>
        <h2 className="mt-1 text-lg font-semibold text-white">{entry.audit_action}</h2>
      </div>
      <pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950/70 p-3 text-xs text-slate-300">
        {JSON.stringify(entry.audit_payload_json, null, 2)}
      </pre>
    </section>
  );
}
