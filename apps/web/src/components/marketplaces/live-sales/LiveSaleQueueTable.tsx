import type { LiveSaleQueueItemResponse } from "../../../api/client";

export function LiveSaleQueueTable({
  items,
  canManage,
  busyQueueItemId,
  onUpdateStatus,
}: {
  items: LiveSaleQueueItemResponse[];
  canManage: boolean;
  busyQueueItemId: number | null;
  onUpdateStatus: (
    queueItemId: number,
    itemStatus: "active" | "sold" | "passed" | "removed",
    actualSalePrice?: string | null,
  ) => Promise<void>;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Queue</p>
          <h2 className="mt-1 text-base font-semibold text-white">Run-of-show inventory queue</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No queue items are attached to this session yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Position</th>
                <th className="px-4 py-3">Item</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr key={item.id} className="bg-slate-950/35 text-slate-200">
                  <td className="px-4 py-3 text-sm font-semibold text-white">{item.queue_position}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">Inventory #{item.inventory_item_id}</p>
                    <p className="mt-1 text-xs text-slate-500">Listing draft #{item.marketplace_listing_draft_id}</p>
                    <p className="text-xs text-slate-500">Planned price {item.planned_price ?? "n/a"} · Sold {item.actual_sale_price ?? "n/a"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                      {item.item_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {canManage ? (
                      <div className="flex flex-wrap gap-2">
                        <ActionButton disabled={busyQueueItemId === item.id} onClick={() => void onUpdateStatus(item.id, "active")}>
                          Active
                        </ActionButton>
                        <ActionButton disabled={busyQueueItemId === item.id} onClick={() => void onUpdateStatus(item.id, "sold", item.planned_price ?? null)}>
                          Sold
                        </ActionButton>
                        <ActionButton disabled={busyQueueItemId === item.id} onClick={() => void onUpdateStatus(item.id, "passed")}>
                          Passed
                        </ActionButton>
                        <ActionButton disabled={busyQueueItemId === item.id} onClick={() => void onUpdateStatus(item.id, "removed")}>
                          Removed
                        </ActionButton>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">View only</p>
                    )}
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

function ActionButton({
  children,
  disabled,
  onClick,
}: {
  children: string;
  disabled: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-2xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}
