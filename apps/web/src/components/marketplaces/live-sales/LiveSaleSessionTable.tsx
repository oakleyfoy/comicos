import type { LiveSaleSessionResponse } from "../../../api/client";

export function LiveSaleSessionTable({
  items,
  selectedSessionId,
  onSelect,
}: {
  items: LiveSaleSessionResponse[];
  selectedSessionId: number | null;
  onSelect: (sessionId: number) => void;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Sessions</p>
          <h2 className="mt-1 text-base font-semibold text-white">Live-sale planning queue</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No live-sale sessions have been created yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Session</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Timing</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer bg-slate-950/35 text-slate-200 ${selectedSessionId === item.id ? "ring-1 ring-violet-400/30" : ""}`}
                  onClick={() => onSelect(item.id)}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{item.session_name}</p>
                    <p className="mt-1 text-xs text-slate-500">Marketplace account #{item.marketplace_account_id}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                      {item.session_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    <p>Planned start: {item.planned_start_at ? new Date(item.planned_start_at).toLocaleString() : "n/a"}</p>
                    <p>Planned end: {item.planned_end_at ? new Date(item.planned_end_at).toLocaleString() : "n/a"}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
