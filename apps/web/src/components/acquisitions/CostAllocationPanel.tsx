import { useState } from "react";

import { ApiError, apiClient, type AcquisitionRead } from "../../api/client";

type Props = {
  acquisition: AcquisitionRead;
  onAllocated: () => void;
};

export function CostAllocationPanel({ acquisition, onAllocated }: Props): JSX.Element {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const summary = acquisition.inventory_summary;
  const allocate = async (mode: "EVEN") => {
    setBusy(true);
    setError(null);
    try {
      await apiClient.allocateAcquisition(acquisition.id, mode);
      onAllocated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not allocate costs.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-label="Cost allocation" className="rounded-2xl border border-slate-700 bg-slate-900/60 p-4">
      <h2 className="text-lg font-semibold text-white">Cost Allocation</h2>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-slate-400">Acquisition total</dt>
          <dd className="font-semibold text-white">${summary.acquisition_total}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Allocated</dt>
          <dd className="font-semibold text-white">${summary.allocated_total}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Unallocated</dt>
          <dd className="font-semibold text-white">${summary.unallocated}</dd>
        </div>
      </dl>
      {!summary.fully_allocated ? (
        <p className="mt-2 rounded-lg bg-amber-500/15 px-3 py-2 text-sm text-amber-200">
          Allocated total does not match the acquisition total yet.
        </p>
      ) : (
        <p className="mt-2 rounded-lg bg-emerald-500/15 px-3 py-2 text-sm text-emerald-200">
          Fully allocated.
        </p>
      )}
      {error ? (
        <p role="alert" className="mt-2 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => allocate("EVEN")}
          disabled={busy || acquisition.status !== "OPEN"}
          className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
        >
          Allocate Evenly
        </button>
        <button
          type="button"
          disabled
          title="Manual per-copy editing coming soon"
          className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-500"
        >
          Edit Individual Costs
        </button>
      </div>
    </section>
  );
}
