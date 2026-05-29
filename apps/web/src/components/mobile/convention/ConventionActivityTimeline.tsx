export function ConventionActivityTimeline({
  activities,
}: {
  activities: import("../../../api/client").ConventionActivityResponse[];
}): JSX.Element {
  if (activities.length === 0) {
    return <p className="text-sm text-slate-400">No convention activities logged.</p>;
  }
  return (
    <ol className="space-y-2">
      {activities.map((row) => (
        <li key={row.id} className="rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-200">
          {row.activity_type} <span className="text-slate-500">session #{row.convention_session_id}</span>
        </li>
      ))}
    </ol>
  );
}
