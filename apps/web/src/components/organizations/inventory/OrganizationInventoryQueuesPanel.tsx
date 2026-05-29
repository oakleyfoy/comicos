import type { OrganizationInventoryQueueResponse } from "../../../api/client";

const QUEUE_LABELS: Record<string, string> = {
  intake: "Intake",
  grading_review: "Grading review",
  scan_review: "Scan review",
  marketplace_ready: "Marketplace ready",
  archived: "Archived",
};

type Props = {
  queues: OrganizationInventoryQueueResponse[];
};

export function OrganizationInventoryQueuesPanel({ queues }: Props): JSX.Element {
  const grouped = queues.reduce<Record<string, OrganizationInventoryQueueResponse[]>>((acc, row) => {
    acc[row.queue_name] = acc[row.queue_name] ?? [];
    acc[row.queue_name].push(row);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white">Operational queues</h3>
      {Object.keys(grouped).length === 0 ? <p className="text-sm text-slate-500">No active queue rows.</p> : null}
      {Object.entries(grouped).map(([queueName, rows]) => (
        <div key={queueName} className="rounded-xl border border-white/10 bg-slate-950/35 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{QUEUE_LABELS[queueName] ?? queueName}</p>
          <ol className="mt-2 space-y-1 text-sm text-slate-200">
            {rows
              .slice()
              .sort((a, b) => a.queue_position - b.queue_position)
              .map((row) => (
                <li key={row.id}>
                  #{row.queue_position} · copy {row.inventory_item_id}
                </li>
              ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
