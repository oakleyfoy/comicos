import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import type { LiveSaleSessionCreateRequest, MarketplaceAccountResponse } from "../../../api/client";

export function LiveSaleSessionForm({
  accounts,
  canManage,
  submitting,
  onSubmit,
}: {
  accounts: MarketplaceAccountResponse[];
  canManage: boolean;
  submitting: boolean;
  onSubmit: (payload: LiveSaleSessionCreateRequest) => Promise<void>;
}): JSX.Element {
  const defaultAccountId = accounts[0]?.id ?? 0;
  const [marketplaceAccountId, setMarketplaceAccountId] = useState(String(defaultAccountId));
  const [sessionName, setSessionName] = useState("Whatnot live sale");
  const [plannedStartAt, setPlannedStartAt] = useState("");
  const [plannedEndAt, setPlannedEndAt] = useState("");

  useEffect(() => {
    if (defaultAccountId > 0) {
      setMarketplaceAccountId(String(defaultAccountId));
    }
  }, [defaultAccountId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    await onSubmit({
      marketplace_account_id: Number(marketplaceAccountId),
      session_name: sessionName.trim(),
      planned_start_at: plannedStartAt.trim() ? new Date(plannedStartAt).toISOString() : null,
      planned_end_at: plannedEndAt.trim() ? new Date(plannedEndAt).toISOString() : null,
    });
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Session planner</p>
          <h2 className="mt-1 text-base font-semibold text-white">Create a live-sale session</h2>
        </div>
        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">No Whatnot connect button</p>
      </div>
      <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Marketplace account</span>
          <select
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={marketplaceAccountId}
            onChange={(event) => setMarketplaceAccountId(event.target.value)}
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Session name</span>
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={sessionName}
            onChange={(event) => setSessionName(event.target.value)}
            placeholder="Saturday comic sale"
          />
        </label>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Planned start</span>
            <input
              type="datetime-local"
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={plannedStartAt}
              onChange={(event) => setPlannedStartAt(event.target.value)}
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Planned end</span>
            <input
              type="datetime-local"
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={plannedEndAt}
              onChange={(event) => setPlannedEndAt(event.target.value)}
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={!canManage || submitting || accounts.length === 0}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Creating..." : "Create session"}
        </button>
      </form>
    </section>
  );
}
