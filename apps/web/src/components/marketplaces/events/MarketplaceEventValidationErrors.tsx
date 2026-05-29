import type { MarketplaceEventValidationErrorResponse } from "../../../api/client";

export function MarketplaceEventValidationErrors({
  errors,
}: {
  errors: MarketplaceEventValidationErrorResponse[];
}): JSX.Element {
  if (!errors.length) {
    return (
      <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
        <p className="text-sm text-slate-400">No validation errors.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Validation errors</p>
      <div className="mt-3 space-y-2">
        {errors.map((error) => (
          <div key={`${error.code}:${error.message}`} className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-3 py-2">
            <p className="text-sm font-semibold text-rose-100">{error.code}</p>
            <p className="text-sm text-rose-100/90">{error.message}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
