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
      if (err instanceof ApiError && err.status === 401) return;
      setError(err instanceof ApiError ? err.message : "Could not allocate costs.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      aria-label="Cost allocation"
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-lg font-semibold text-patriot-navy">Cost Allocation</h2>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-slate-500">Acquisition total</dt>
          <dd className="font-semibold text-slate-900">${summary.acquisition_total}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Allocated</dt>
          <dd className="font-semibold text-slate-900">${summary.allocated_total}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Unallocated</dt>
          <dd className="font-semibold text-slate-900">${summary.unallocated}</dd>
        </div>
      </dl>
      {!summary.fully_allocated ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Allocated total does not match the acquisition total yet.
        </p>
      ) : (
        <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Fully allocated.
        </p>
      )}
      {error ? (
        <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => allocate("EVEN")}
          disabled={
            busy ||
            acquisition.status !== "OPEN" ||
            acquisition.item_count === 0 ||
            summary.fully_allocated
          }
          className="rounded-lg bg-patriot-blue px-4 py-2 text-sm font-semibold text-white hover:bg-blue-900 disabled:opacity-50"
        >
          Allocate Evenly
        </button>
        <button
          type="button"
          disabled
          title="Manual per-copy editing coming soon"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-500"
        >
          Edit Individual Costs
        </button>
      </div>
    </section>
  );
}
