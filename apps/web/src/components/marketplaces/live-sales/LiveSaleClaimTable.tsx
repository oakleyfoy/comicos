import type { LiveSaleClaimResponse, LiveSaleClaimSummaryResponse } from "../../../api/client";

export function LiveSaleClaimTable({
  items,
  summary,
  canManage,
  busyClaimId,
  onUpdateStatus,
}: {
  items: LiveSaleClaimResponse[];
  summary: LiveSaleClaimSummaryResponse | null;
  canManage: boolean;
  busyClaimId: number | null;
  onUpdateStatus: (claimId: number, claimStatus: "claimed" | "confirmed" | "cancelled") => Promise<void>;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Claims</p>
          <h2 className="mt-1 text-base font-semibold text-white">Claim tracking</h2>
        </div>
        <p className="text-sm text-slate-400">{summary?.total_claims ?? items.length} total</p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Metric label="Claimed" value={String(summary?.claimed_claims ?? 0)} />
        <Metric label="Confirmed" value={String(summary?.confirmed_claims ?? 0)} />
        <Metric label="Cancelled" value={String(summary?.cancelled_claims ?? 0)} />
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No claims have been recorded yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Buyer</th>
                <th className="px-4 py-3">Claim</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr key={item.id} className="bg-slate-950/35 text-slate-200">
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{item.buyer_identifier}</p>
                    <p className="mt-1 text-xs text-slate-500">Queue item #{item.live_sale_queue_item_id}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    <p>Price {item.claimed_price ?? "n/a"}</p>
                    <p>Claimed {new Date(item.claimed_at).toLocaleString()}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                      {item.claim_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {canManage ? (
                      <div className="flex flex-wrap gap-2">
                        <ActionButton disabled={busyClaimId === item.id} onClick={() => void onUpdateStatus(item.id, "claimed")}>
                          Claimed
                        </ActionButton>
                        <ActionButton disabled={busyClaimId === item.id} onClick={() => void onUpdateStatus(item.id, "confirmed")}>
                          Confirmed
                        </ActionButton>
                        <ActionButton disabled={busyClaimId === item.id} onClick={() => void onUpdateStatus(item.id, "cancelled")}>
                          Cancelled
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

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
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
