import { EmptyState } from "../../EmptyState";
import type { OrganizationComplianceEventResponse } from "../../../api/client";

type Props = {
  events: OrganizationComplianceEventResponse[];
};

function severityTone(severity: string): string {
  switch (severity) {
    case "critical":
      return "border-rose-400/35 bg-rose-500/15 text-rose-100";
    case "elevated":
      return "border-amber-400/35 bg-amber-500/15 text-amber-100";
    case "warning":
      return "border-yellow-400/35 bg-yellow-500/15 text-yellow-100";
    default:
      return "border-cyan-400/35 bg-cyan-500/15 text-cyan-100";
  }
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function OrganizationCompliancePanel({ events }: Props): JSX.Element {
  if (!events.length) {
    return <EmptyState title="No compliance events" description="Compliance events will appear here when elevated or critical organization actions are projected." />;
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Compliance</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Compliance events</h2>
      </div>
      <div className="mt-4 space-y-3">
        {events.map((event) => (
          <div key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium text-white">{event.compliance_event_type}</p>
                <div className="mt-2">
                  <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${severityTone(event.severity_level)}`}>
                    {event.severity_level}
                  </span>
                </div>
              </div>
              <p className="text-xs text-slate-400">{formatDateTime(event.created_at)}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
