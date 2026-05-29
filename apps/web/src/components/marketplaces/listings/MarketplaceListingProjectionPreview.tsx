import type { MarketplaceListingProjectionResponse } from "../../../api/client";

type Props = {
  projections: MarketplaceListingProjectionResponse[];
};

export function MarketplaceListingProjectionPreview({ projections }: Props): JSX.Element {
  const current = projections.find((row) => row.projection_status === "current") ?? projections[0] ?? null;
  if (!current) {
    return (
      <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-sm text-slate-500">
        No marketplace payload projection generated yet.
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Projection preview</p>
      <p className="mt-1 text-sm text-slate-300">
        {current.marketplace_type} · {current.projection_status} · {new Date(current.generated_at).toLocaleString()}
      </p>
      <pre className="mt-3 max-h-80 overflow-auto rounded-xl bg-black/40 p-3 text-xs text-emerald-100">
        {JSON.stringify(current.projection_payload_json, null, 2)}
      </pre>
    </div>
  );
}
