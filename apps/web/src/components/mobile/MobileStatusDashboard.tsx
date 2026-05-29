function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function MobileStatusDashboard({
  summary,
  runtimeRegistry,
}: {
  summary: Record<string, unknown>;
  runtimeRegistry: Record<string, unknown>;
}): JSX.Element {
  const devices = (summary["devices"] ?? {}) as Record<string, number>;
  const sessions = (summary["sessions"] ?? {}) as Record<string, number>;
  const contracts = (summary["contracts"] ?? {}) as Record<string, number>;
  const deviceStatuses = (runtimeRegistry["device_statuses"] ?? []) as string[];
  const sessionStatuses = (runtimeRegistry["session_statuses"] ?? []) as string[];
  const contractTypes = (runtimeRegistry["sync_contract_types"] ?? []) as string[];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Devices" value={String(devices.total ?? 0)} />
        <StatCard label="Active devices" value={String(devices.active ?? 0)} />
        <StatCard label="Sessions" value={String(sessions.total ?? 0)} />
        <StatCard label="Contracts" value={String(contracts.total ?? 0)} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-white/10 p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Device statuses</p>
          <p className="mt-2 text-sm text-slate-200">{deviceStatuses.join(", ") || "—"}</p>
        </div>
        <div className="rounded-2xl border border-white/10 p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Session statuses</p>
          <p className="mt-2 text-sm text-slate-200">{sessionStatuses.join(", ") || "—"}</p>
        </div>
        <div className="rounded-2xl border border-white/10 p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Contract types</p>
          <p className="mt-2 text-sm text-slate-200">{contractTypes.join(", ") || "—"}</p>
        </div>
      </div>
    </div>
  );
}
