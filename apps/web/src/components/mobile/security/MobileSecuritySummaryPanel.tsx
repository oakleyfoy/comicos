import type { MobileDeviceSecurityDashboardResponse } from "../../../api/client";

export function MobileSecuritySummaryPanel({ dashboard }: { dashboard: MobileDeviceSecurityDashboardResponse }): JSX.Element {
  const trustSummary = (dashboard.summary["trust_states"] ?? {}) as Record<string, unknown>;
  const policySummary = (dashboard.summary["policies"] ?? {}) as Record<string, unknown>;
  const accessSummary = (dashboard.summary["access_logs"] ?? {}) as Record<string, unknown>;
  const diagnosticSummary = (dashboard.summary["diagnostics"] ?? {}) as Record<string, unknown>;
  const cards = [
    { label: "Trusted devices", value: String(trustSummary["trusted"] ?? 0) },
    { label: "Suspended devices", value: String(trustSummary["suspended"] ?? 0) },
    { label: "Active policies", value: String(policySummary["active"] ?? 0) },
    { label: "Denied access", value: String(accessSummary["denied"] ?? 0) },
    { label: "Warnings", value: String(diagnosticSummary["warning"] ?? 0) },
    { label: "Errors", value: String(diagnosticSummary["error"] ?? 0) },
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        {cards.map((card) => (
          <div key={card.label} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{card.label}</p>
            <p className="mt-2 text-2xl font-semibold text-white">{card.value}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-3 xl:grid-cols-2">
        {dashboard.diagnostics.map((diagnostic) => (
          <div key={diagnostic.diagnostic_code} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">{diagnostic.diagnostic_code}</p>
              <span className="rounded-full border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.14em] text-slate-300">
                {diagnostic.diagnostic_status}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-300">{diagnostic.diagnostic_message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
