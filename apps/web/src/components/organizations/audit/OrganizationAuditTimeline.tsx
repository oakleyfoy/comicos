import { EmptyState } from "../../EmptyState";
import type { OrganizationAuditLedgerResponse } from "../../../api/client";

type Props = {
  entries: OrganizationAuditLedgerResponse[];
  selectedEntryId: number | null;
  onSelect: (entryId: number) => void;
};

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function OrganizationAuditTimeline({ entries, selectedEntryId, onSelect }: Props): JSX.Element {
  if (!entries.length) {
    return <EmptyState title="No audit entries" description="Immutable organization audit rows will appear here as operational workflows execute." />;
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Audit ledger</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Organization audit timeline</h2>
      </div>
      <div className="mt-4 space-y-3">
        {entries.map((entry) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => onSelect(entry.id)}
            className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
              selectedEntryId === entry.id
                ? "border-cyan-400/40 bg-cyan-500/10"
                : "border-white/10 bg-slate-950/40 hover:bg-white/5"
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium text-white">{entry.audit_action}</p>
                <p className="mt-1 text-sm text-slate-400">
                  {entry.audit_category} · {entry.resource_type}
                  {entry.resource_id ? ` #${entry.resource_id}` : ""}
                </p>
                <p className="mt-1 text-xs text-slate-500">Actor {entry.actor_user_id ?? "system"}</p>
              </div>
              <p className="text-xs text-slate-400">{formatDateTime(entry.created_at)}</p>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
