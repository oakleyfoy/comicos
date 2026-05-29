export function ConventionSummaryCards({ summary }: { summary: Record<string, unknown> }): JSX.Element {
  const sessions = (summary["sessions"] ?? {}) as Record<string, number>;
  const booths = (summary["booths"] ?? {}) as Record<string, number>;
  const staged = (summary["inventory_staged"] ?? {}) as Record<string, number>;
  const activities = (summary["activities"] ?? {}) as Record<string, number>;
  const cards = [
    { label: "Sessions", value: String(sessions.total ?? 0) },
    { label: "Active sessions", value: String(sessions.active ?? 0) },
    { label: "Booths", value: String(booths.total ?? 0) },
    { label: "Staged items", value: String(staged.total ?? 0) },
    { label: "Activities", value: String(activities.total ?? 0) },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => (
        <div key={card.label} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{card.label}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{card.value}</p>
        </div>
      ))}
    </div>
  );
}
