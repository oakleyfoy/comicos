import type { OrganizationActivityEventResponse } from "../../../api/client";

type Props = {
  events: OrganizationActivityEventResponse[];
};

export function OrganizationActivityTimeline({ events }: Props): JSX.Element {
  if (!events.length) {
    return <p className="text-sm text-slate-500">No activity recorded for this organization yet.</p>;
  }
  return (
    <ol className="space-y-3">
      {events.map((event) => (
        <li
          key={event.id}
          className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-slate-200"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-medium text-white">
              {event.activity_type}
              {event.category ? (
                <span className="ml-2 rounded-full border border-white/10 px-2 py-0.5 text-xs font-normal text-slate-400">
                  {event.category}
                </span>
              ) : null}
            </p>
            <time className="text-xs text-slate-500">{new Date(event.created_at).toLocaleString()}</time>
          </div>
          {event.actor_user_id ? (
            <p className="mt-1 text-xs text-slate-500">Actor user #{event.actor_user_id}</p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
