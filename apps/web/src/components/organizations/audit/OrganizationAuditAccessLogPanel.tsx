import { EmptyState } from "../../EmptyState";
import type { OrganizationAuditAccessLogResponse } from "../../../api/client";

type Props = {
  rows: OrganizationAuditAccessLogResponse[];
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

export function OrganizationAuditAccessLogPanel({ rows }: Props): JSX.Element {
  if (!rows.length) {
    return <EmptyState title="No access logs" description="Audit access attempts will appear here when users query organization audit data." />;
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Access log</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Audit access attempts</h2>
      </div>
      <div className="mt-4 space-y-3">
        {rows.map((row) => (
          <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium text-white">{row.accessed_resource_type}</p>
                <p className="mt-1 text-sm text-slate-400">
                  Actor {row.actor_user_id} · {row.access_result}
                  {row.accessed_resource_id ? ` · ${row.accessed_resource_id}` : ""}
                </p>
              </div>
              <p className="text-xs text-slate-400">{formatDateTime(row.created_at)}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
