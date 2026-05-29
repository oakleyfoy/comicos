function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function MobileFoundationEventTimeline({
  events,
}: {
  events: import("../../api/client").MobileFoundationEventResponse[];
}): JSX.Element {
  if (events.length === 0) {
    return <p className="text-sm text-slate-400">No foundation events yet.</p>;
  }
  return (
    <ol className="space-y-3">
      {events.map((event) => (
        <li key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-white">{event.event_type}</p>
            <p className="text-xs text-slate-500">{formatDateTime(event.created_at)}</p>
          </div>
          <p className="mt-1 font-mono text-[11px] text-slate-500">#{event.id}</p>
        </li>
      ))}
    </ol>
  );
}
