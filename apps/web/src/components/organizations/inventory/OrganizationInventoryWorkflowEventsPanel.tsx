import type { OrganizationInventoryWorkflowEventResponse } from "../../../api/client";

type Props = {
  events: OrganizationInventoryWorkflowEventResponse[];
  canView: boolean;
};

export function OrganizationInventoryWorkflowEventsPanel({ events, canView }: Props): JSX.Element {
  if (!canView) {
    return <p className="text-sm text-slate-500">Audit permission is required to view workflow lineage.</p>;
  }
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white">Workflow lineage</h3>
      {!events.length ? <p className="text-sm text-slate-500">No workflow events recorded yet.</p> : null}
      <ul className="max-h-72 space-y-2 overflow-y-auto pr-1 text-sm">
        {events.map((event) => (
          <li key={event.id} className="rounded-lg border border-white/10 bg-slate-950/40 px-3 py-2">
            <p className="font-medium text-white">{event.workflow_event_type}</p>
            <p className="text-xs text-slate-500">
              copy {event.inventory_item_id ?? "—"} · {new Date(event.created_at).toLocaleString()}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
