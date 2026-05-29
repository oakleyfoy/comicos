export function ScanEventTimeline({
  events,
}: {
  events: import("../../../api/client").ScanEventResponse[];
}): JSX.Element {
  if (events.length === 0) {
    return <p className="text-sm text-slate-400">No scan events yet.</p>;
  }
  return (
    <ol className="space-y-3">
      {events.map((event) => (
        <li key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3">
          <p className="text-sm font-medium text-white">{event.event_type}</p>
        </li>
      ))}
    </ol>
  );
}
