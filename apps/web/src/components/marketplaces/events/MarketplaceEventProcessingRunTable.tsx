import type { MarketplaceEventProcessingRunResponse } from "../../../api/client";

export function MarketplaceEventProcessingRunTable({
  items,
}: {
  items: MarketplaceEventProcessingRunResponse[];
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Processing runs</p>
          <h2 className="mt-1 text-base font-semibold text-white">Deterministic processing execution</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No processing runs yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Run</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Timing</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr key={item.id} className="bg-slate-950/35 text-slate-200">
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">Event #{item.marketplace_event_id}</p>
                    <pre className="mt-1 overflow-auto text-xs text-slate-500">
                      {JSON.stringify(item.processing_result_json, null, 2)}
                    </pre>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                      {item.processing_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    <p>Started: {new Date(item.started_at).toLocaleString()}</p>
                    <p>Completed: {item.completed_at ? new Date(item.completed_at).toLocaleString() : "n/a"}</p>
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
