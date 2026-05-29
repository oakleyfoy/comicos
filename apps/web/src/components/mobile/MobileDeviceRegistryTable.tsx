function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function MobileDeviceStatusBadge({ status }: { status: string }): JSX.Element {
  const tone =
    status === "active"
      ? "border-emerald-400/40 text-emerald-100"
      : status === "suspended"
        ? "border-rose-400/40 text-rose-100"
        : "border-slate-400/40 text-slate-200";
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] uppercase tracking-wide ${tone}`}>{status}</span>
  );
}

export function MobileDeviceRegistryTable({
  items,
}: {
  items: import("../../api/client").MobileDeviceResponse[];
}): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No registered devices yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="border-b border-white/10 bg-slate-950/60 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Identifier</th>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Last seen</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id} className="border-b border-white/5 last:border-0">
              <td className="px-4 py-3 font-medium text-white">{row.device_name}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-400">{row.device_identifier}</td>
              <td className="px-4 py-3">{row.device_type}</td>
              <td className="px-4 py-3">
                <MobileDeviceStatusBadge status={row.device_status} />
              </td>
              <td className="px-4 py-3 text-slate-400">{formatDateTime(row.last_seen_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
