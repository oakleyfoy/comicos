export function MobileAnalyticsOverviewPanels({ summary }: { summary: Record<string, unknown> }): JSX.Element {
  const sections = Object.entries(summary) as Array<[string, Record<string, unknown>]>;

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      {sections.map(([sectionKey, values]) => (
        <section key={sectionKey} className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
          <h2 className="text-lg font-semibold capitalize text-white">{sectionKey.replace(/_/g, " ")}</h2>
          <div className="mt-4 space-y-3">
            {Object.entries(values).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between gap-3 rounded-2xl border border-white/5 bg-slate-950/45 px-3 py-2">
                <span className="text-sm text-slate-400">{key.replace(/_/g, " ")}</span>
                <span className="text-sm font-semibold text-white">{String(value)}</span>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
