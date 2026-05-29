export function MobileOpsSummaryPanels({ summary }: { summary: Record<string, unknown> }): JSX.Element {
  const sections = [
    { key: "devices", label: "Devices / Sessions" },
    { key: "offline", label: "Offline Inventory" },
    { key: "scanning", label: "Scanning" },
    { key: "convention", label: "Convention" },
    { key: "quick_sales", label: "Quick Sales" },
    { key: "workflow_health", label: "Workflow Health" },
  ];

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      {sections.map((section) => {
        const values = (summary[section.key] ?? {}) as Record<string, unknown>;
        return (
          <section key={section.key} className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
            <h2 className="text-lg font-semibold text-white">{section.label}</h2>
            <div className="mt-4 space-y-2">
              {Object.entries(values).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3">
                  <span className="text-sm text-slate-300">{key.replace(/_/g, " ")}</span>
                  <span className="text-sm font-semibold text-white">
                    {typeof value === "object" && value !== null ? JSON.stringify(value) : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
