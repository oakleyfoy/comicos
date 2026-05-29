import type { MarketplaceOfferSummaryResponse } from "../../../api/client";

export function MarketplaceOfferSummaryPanel({
  summary,
}: {
  summary: MarketplaceOfferSummaryResponse | null;
}): JSX.Element {
  const total = summary?.total_offers ?? 0;
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Offer summary</p>
          <h2 className="mt-1 text-base font-semibold text-white">Internal offer tracking</h2>
        </div>
        <p className="text-sm text-slate-400">{total} total</p>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Metric label="Received" value={summary?.received_offers ?? 0} />
        <Metric label="Reviewed" value={summary?.reviewed_offers ?? 0} />
        <Metric label="Accepted internal" value={summary?.accepted_internal_offers ?? 0} />
        <Metric label="Rejected internal" value={summary?.rejected_internal_offers ?? 0} />
        <Metric label="Expired" value={summary?.expired_offers ?? 0} />
        <Metric label="Total" value={total} />
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}
