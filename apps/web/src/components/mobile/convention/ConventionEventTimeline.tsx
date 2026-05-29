export function ConventionEventTimeline({
  events,
}: {
  events: import("../../../api/client").ConventionEventResponse[];
}): JSX.Element {
  if (events.length === 0) {
    return <p className="text-sm text-slate-400">No convention events yet.</p>;
  }
  return (
    <ol className="space-y-2">
      {events.map((event) => (
        <li key={event.id} className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white">
          {event.event_type}
        </li>
      ))}
    </ol>
  );
}
