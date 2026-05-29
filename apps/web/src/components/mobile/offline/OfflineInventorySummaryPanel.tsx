function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function OfflineInventorySummaryPanel({
  summary,
  runtimeRegistry,
}: {
  summary: Record<string, unknown>;
  runtimeRegistry: Record<string, unknown>;
}): JSX.Element {
  const records = (summary["records"] ?? {}) as Record<string, number>;
  const changes = (summary["changes"] ?? {}) as Record<string, number>;
  const queue = (summary["queue"] ?? {}) as Record<string, number>;
  const conflicts = (summary["conflicts"] ?? {}) as Record<string, number>;
  const queueStatuses = (runtimeRegistry["queue_statuses"] ?? []) as string[];
  const changeTypes = (runtimeRegistry["change_types"] ?? []) as string[];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Records" value={String(records.total ?? 0)} />
        <StatCard label="Changes" value={String(changes.total ?? 0)} />
        <StatCard label="Queue pending" value={String(queue.pending ?? 0)} />
        <StatCard label="Open conflicts" value={String(conflicts.open ?? 0)} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/10 p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Queue statuses</p>
          <p className="mt-2 text-sm text-slate-200">{queueStatuses.join(", ") || "—"}</p>
        </div>
        <div className="rounded-2xl border border-white/10 p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Change types</p>
          <p className="mt-2 text-sm text-slate-200">{changeTypes.join(", ") || "—"}</p>
        </div>
      </div>
    </div>
  );
}
