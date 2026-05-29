import { useState } from "react";
import type { FormEvent } from "react";

import type { LiveSaleQueueReorderRequest } from "../../../api/client";

export function LiveSaleQueueReorderShell({
  canManage,
  submitting,
  onSubmit,
}: {
  canManage: boolean;
  submitting: boolean;
  onSubmit: (payload: LiveSaleQueueReorderRequest) => Promise<void>;
}): JSX.Element {
  const [queueItemIds, setQueueItemIds] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    const ids = queueItemIds
      .split(",")
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isFinite(value) && value > 0);
    await onSubmit({ queue_item_ids: ids });
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Queue reorder shell</p>
      <h2 className="mt-1 text-base font-semibold text-white">Deterministic run-of-show ordering</h2>
      <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Queue item IDs, comma-separated</span>
          <textarea
            className="min-h-[100px] rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 font-mono text-xs text-slate-100"
            value={queueItemIds}
            onChange={(event) => setQueueItemIds(event.target.value)}
            placeholder="1, 2, 3"
          />
        </label>
        <button
          type="submit"
          disabled={!canManage || submitting}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Reordering..." : "Reorder queue"}
        </button>
      </form>
    </section>
  );
}
